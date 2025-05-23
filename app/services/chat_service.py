import json
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple # Added Tuple
from app.services.mongo_service import db
from app.services.genai_service import (
    generate_conversation_response,
    generate_mongo_query,
    fix_mongo_query,
)
from app.utils.schema_parser import parse_schema_summary
from app.utils.logger import logger
from app.config import settings
from app.models.chat import ConversationEntry, ChatConversationDocument, ErrorHistoryItem

SCHEMA_DIR = settings.schema_dir
CHAT_CONVERSATIONS_COLLECTION_NAME = settings.CHAT_CONVERSATIONS_COLLECTION

def is_mongo_query_request(question: str) -> bool:
    keywords = ["find", "show", "list", "where", "query", "give", "provide"]
    return any(kw in question.lower() for kw in keywords)

def find_matching_parenthesis(s: str, start: int) -> int:
    paren = 0
    for i in range(start, len(s)):
        if s[i] == "(":
            paren += 1
        elif s[i] == ")":
            if paren == 0:
                return i
            paren -= 1
    return -1

def split_filter_projection(args_str: str):
    if ',' not in args_str:
        return args_str, ""
    brace_level = 0
    boundary = -1
    for i, ch in enumerate(args_str):
        if ch == "{":
            brace_level += 1
        elif ch == "}":
            brace_level -= 1
            if brace_level == 0:
                boundary = i
                break
    if boundary == -1: # No closing brace for the first object found
        return args_str, "" # Assume it's all filter or a malformed query
    filter_part = args_str[:boundary+1].strip()
    remainder = args_str[boundary+1:].strip()
    if remainder.startswith(','):
        remainder = remainder[1:].strip()
    return filter_part, remainder

def execute_mongo_queries(query_string: str):
    pattern = r"(db\.[a-zA-Z0-9_]+\.find\s*\((.*?)\)(?:\.limit\s*\(\s*(\d+)\s*\))?)"
    matches = re.findall(pattern, query_string, flags=re.DOTALL)

    if not matches:
        if query_string.startswith("db.") and ".find(" in query_string:
            try:
                coll_part = query_string.split(".find(")[0].replace("db.", "")
                args_part_full = query_string.split(".find(")[1]
                
                limit_val_simple = 10
                limit_match_simple = re.search(r"\)\.limit\s*\(\s*(\d+)\s*\)$", args_part_full)
                if limit_match_simple:
                    limit_val_simple = int(limit_match_simple.group(1))
                    args_part_full = args_part_full[:limit_match_simple.start()]

                if not args_part_full.endswith(")"):
                    return None, "Malformed find() arguments in simple parse."
                
                args_part = args_part_full[:-1]
                matches = [(query_string, args_part, str(limit_val_simple) if limit_match_simple else "")]
            except Exception as e:
                logger.error(f"Simple query parse error: {e} for query: {query_string}")
                return None, "Invalid query format for simple parsing."
        else:
            logger.warning(f"No valid MongoDB query found in string: {query_string}")
            return None, "Invalid query format or no queries found matching pattern."

    all_query_results = []
    for full_match_str, inner_args_str, limit_str in matches:
        m_coll = re.match(r"db\.([^.]+)\.find", full_match_str.strip())
        if not m_coll:
            return None, f"Could not extract collection from {full_match_str}"
        coll_name = m_coll.group(1)

        filt_str, proj_str = split_filter_projection(inner_args_str.strip())
        
        try:
            filt = json.loads(filt_str) if filt_str else {}
        except Exception as e:
            logger.error(f"Error parsing filter '{filt_str}': {e}")
            return None, f"Error parsing filter '{filt_str}': {e}"
        
        proj = None
        if proj_str:
            try:
                proj = json.loads(proj_str)
            except Exception as e:
                logger.error(f"Error parsing projection '{proj_str}': {e}")
                return None, f"Error parsing projection '{proj_str}': {e}"
        
        limit_val = int(limit_str) if limit_str and limit_str.isdigit() else 10

        try:
            cursor = db[coll_name].find(filt, proj).limit(limit_val)
            results_list = list(cursor)
            for doc in results_list:
                if "_id" in doc:
                    doc.pop("_id", None) # Remove _id from each document
        except Exception as e:
            logger.error(f"MongoDB execution error for collection '{coll_name}': {e}")
            return None, f"MongoDB execution error for collection '{coll_name}': {e}"

        all_query_results.append({
            "collection": coll_name,
            "filter": filt,
            "projection": proj,
            "results": results_list
        })
    return all_query_results, None

def execute_mongo_with_retries(question: str, query_string: str, schema_data: dict, max_retries=3):
    attempts = 0
    error_history_list_of_dicts: List[Dict[str, Any]] = []
    current_query_string = query_string

    while attempts < max_retries:
        results, error = execute_mongo_queries(current_query_string)
        if error:
            attempts += 1
            error_item_dict: Dict[str, Any] = {
                "attempt": attempts,
                "query": current_query_string,
                "error": str(error)
            }
            error_history_list_of_dicts.append(error_item_dict)
            
            logger.info(f"Attempt {attempts} failed for query: {current_query_string}. Error: {error}")
            fixed_query_string = fix_mongo_query(question, current_query_string, str(error), schema_data)
            
            if fixed_query_string and fixed_query_string.strip() and fixed_query_string.lower() != "i'm sorry, i couldn't found any result." and fixed_query_string != current_query_string :
                logger.info(f"Fix suggested: {fixed_query_string}")
                error_history_list_of_dicts[-1]["fix"] = fixed_query_string
                current_query_string = fixed_query_string
            else:
                logger.warning(f"No fix suggested or fix was same/invalid for: {current_query_string}")
                break 
        else: # Success
            error_history_models = [ErrorHistoryItem(**item) for item in error_history_list_of_dicts]
            return results, None, error_history_models
            
    final_error_message = error_history_list_of_dicts[-1]["error"] if error_history_list_of_dicts else "Failed to execute MongoDB query after multiple attempts."
    error_history_models = [ErrorHistoryItem(**item) for item in error_history_list_of_dicts]
    return None, final_error_message, error_history_models

def format_conversation_history_for_llm(
    conversation_entries: List[ConversationEntry], # ConversationEntry no longer has timestamp
    max_turns: int = 3
) -> str:
    if not conversation_entries:
        return ""
    recent_turns = conversation_entries[-max_turns:]
    memory_lines = []
    for entry in recent_turns:
        memory_lines.append(f"User: {entry.question}")
        if entry.answer:
            if len(entry.answer) == 1 and "type" in entry.answer[0] and entry.answer[0]["type"] == "text_response":
                memory_lines.append(f"Assistant: {entry.answer[0].get('content', 'Provided a response.')}")
            elif len(entry.answer) == 1 and "type" in entry.answer[0] and entry.answer[0]["type"] == "error":
                memory_lines.append(f"Assistant: Encountered an error - {entry.answer[0].get('message', 'Error occurred.')}")
            elif len(entry.answer) == 1 and "type" in entry.answer[0] and entry.answer[0]["type"] == "no_data":
                 memory_lines.append(f"Assistant: {entry.answer[0].get('message', 'No matching documents found.')}")
            else:
                memory_lines.append(f"Assistant: Provided data based on your query (found {len(entry.answer)} items).")
        else:
            memory_lines.append(f"Assistant: No answer recorded.")
    return "\n".join(memory_lines)

# Modified return type
def process_question(reference_id: str, question: str) -> Tuple[str, List[Dict[str, Any]], Optional[List[ErrorHistoryItem]]]:
    schema_data = parse_schema_summary(SCHEMA_DIR)
    # now_utc = datetime.now(timezone.utc) # No longer needed here for new_qna_entry.timestamp
    current_answer_data: List[Dict[str, Any]]
    found_in_history = False
    llm_memory_context = ""
    error_history_for_current_turn: Optional[List[ErrorHistoryItem]] = None


    # 1. Load existing conversation document
    # Projection {"conversation.timestamp": 0} is no longer needed as timestamp isn't stored in ConversationEntry
    conversation_doc_dict = db[CHAT_CONVERSATIONS_COLLECTION_NAME].find_one({"_id": reference_id})

    existing_conversation_entries: List[ConversationEntry] = []
    loaded_conversation_doc: Optional[ChatConversationDocument] = None

    if conversation_doc_dict:
        try:
            loaded_conversation_doc = ChatConversationDocument.model_validate(conversation_doc_dict)
            if loaded_conversation_doc.conversation:
                 existing_conversation_entries = loaded_conversation_doc.conversation
                 llm_memory_context = format_conversation_history_for_llm(existing_conversation_entries)
        except Exception as e:
            logger.error(f"Error validating existing conversation document for {reference_id}: {e}")

    # 2. Check if the exact question was asked before
    for entry in reversed(existing_conversation_entries):
        if entry.question.strip().lower() == question.strip().lower():
            current_answer_data = entry.answer
            found_in_history = True
            logger.info(f"Exact match: Answer for '{question}' found in history for reference_id '{reference_id}'.")
            # If error history was stored with the answer, you might retrieve it here.
            # For simplicity, assuming error history is not re-served from cache, only for new attempts.
            break

    # 3. If not found in history, process as new
    if not found_in_history:
        logger.info(f"Processing new question '{question}' for reference_id '{reference_id}'.")
        if is_mongo_query_request(question):
            mongo_query_str = generate_mongo_query(question, schema_data, memory=llm_memory_context)
            logger.info(f"Generated MongoDB query: {mongo_query_str}")
            
            raw_results, error, error_history_models = execute_mongo_with_retries(
                question, mongo_query_str, schema_data
            )
            error_history_for_current_turn = error_history_models
            
            flat_data_results = []
            if raw_results:
                for query_result_group in raw_results:
                    if "results" in query_result_group and isinstance(query_result_group["results"], list):
                        flat_data_results.extend(query_result_group["results"])
            
            if error:
                logger.error(f"Error executing MongoDB query for '{question}': {error}")
                error_history_dicts = [item.model_dump(exclude_none=True) for item in error_history_models]
                current_answer_data = [{
                    "type": "error", 
                    "message": str(error), 
                    "query_attempted": mongo_query_str,
                    "history": error_history_dicts 
                }]
            elif not flat_data_results:
                logger.info(f"MongoDB query for '{question}' returned no documents.")
                current_answer_data = [{
                    "type": "no_data",
                    "message": "Your query executed successfully but returned no matching documents.",
                    "query_info": raw_results if raw_results else mongo_query_str
                }]
            else:
                logger.info(f"MongoDB query for '{question}' successful, {len(flat_data_results)} items found.")
                current_answer_data = flat_data_results
        else: # Conversational question
            logger.info(f"Generating direct LLM response for '{question}'.")
            response_text = generate_conversation_response(question, memory=llm_memory_context)
            current_answer_data = [{"type": "text_response", "content": response_text}]

    # 5. Create the new conversation entry for the current turn (data only, model is instantiated later)
    new_qna_entry_data = ConversationEntry(
        # timestamp removed
        question=question,
        answer=current_answer_data
    )

    # 6. Append to existing conversation or create new document
    if loaded_conversation_doc:
        final_conversation_doc_for_db = loaded_conversation_doc
        final_conversation_doc_for_db.conversation.append(new_qna_entry_data)
    else:
        final_conversation_doc_for_db = ChatConversationDocument(
            reference_id=reference_id,
            conversation=[new_qna_entry_data]
        )
        if conversation_doc_dict and not loaded_conversation_doc:
             logger.warning(f"Re-created conversation document for {reference_id} due to validation issue or it was null.")
    
    # 7. Upsert the document
    try:
        update_data = final_conversation_doc_for_db.model_dump(by_alias=True, exclude_none=True)
        
        operations = {"$set": update_data}

        db[CHAT_CONVERSATIONS_COLLECTION_NAME].update_one(
            {"_id": reference_id},
            operations, 
            upsert=True
        )
        status_msg = "Used cached answer" if found_in_history else "Generated new answer"
        logger.info(f"Successfully upserted conversation for reference_id '{reference_id}'. {status_msg}")
    except Exception as e:
        logger.error(f"Failed to upsert conversation for reference_id '{reference_id}': {e}", exc_info=True)

    return question, current_answer_data, error_history_for_current_turn
