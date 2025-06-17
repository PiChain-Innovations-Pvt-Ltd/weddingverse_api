# app/services/chat_service.py - Updated for simple IST timestamps

import json
import re
from datetime import datetime, timezone, timedelta
from dateutil import tz
from typing import List, Dict, Any, Optional, Tuple
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

# Get SCHEMA_DIR from settings to avoid import issues
SCHEMA_DIR = settings.schema_dir
CHAT_CONVERSATIONS_COLLECTION_NAME = settings.CHAT_CONVERSATIONS_COLLECTION
CONVERSATION_HISTORY_RETENTION_DAYS = 30

# Simple IST timestamp utility
def get_ist_timestamp() -> str:
    """Get current timestamp in IST format: YYYY-MM-DD HH:MM:SS"""
    ist = tz.gettz("Asia/Kolkata")
    return datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

def parse_ist_timestamp(timestamp_str: str) -> datetime:
    """Parse IST timestamp string back to datetime object for comparison"""
    try:
        ist = tz.gettz("Asia/Kolkata")
        dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        # Make it timezone-aware in IST
        return dt.replace(tzinfo=ist)
    except:
        # Fallback to current time if parsing fails
        return datetime.now(tz.gettz("Asia/Kolkata"))

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
    if boundary == -1:
        return args_str, ""
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
                    doc.pop("_id", None)
        except Exception as e:
            logger.error(f"MongoDB execution error for collection '{coll_name}': {e}")
            return None, f"MongoDB execution error for collection '{coll_name}': {e}"
        all_query_results.append({"collection": coll_name, "filter": filt, "projection": proj, "results": results_list})
    return all_query_results, None

def execute_mongo_with_retries(question: str, query_string: str, schema_data: dict, max_retries=3):
    attempts = 0
    error_history_list_of_dicts: List[Dict[str, Any]] = []
    current_query_string = query_string
    while attempts < max_retries:
        results, error = execute_mongo_queries(current_query_string)
        if error:
            attempts += 1
            error_item_dict: Dict[str, Any] = {"attempt": attempts, "query": current_query_string, "error": str(error)}
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
        else:
            error_history_models = [ErrorHistoryItem(**item) for item in error_history_list_of_dicts]
            return results, None, error_history_models
    final_error_message = error_history_list_of_dicts[-1]["error"] if error_history_list_of_dicts else "Failed to execute MongoDB query after multiple attempts."
    error_history_models = [ErrorHistoryItem(**item) for item in error_history_list_of_dicts]
    return None, final_error_message, error_history_models

def format_conversation_history_for_llm(
    conversation_entries: List[ConversationEntry],
    max_turns: int = 5
) -> str:
    if not conversation_entries:
        return ""
    recent_turns = conversation_entries[-max_turns:]
    memory_lines = []
    for entry in recent_turns:
        memory_lines.append(f"User: {entry.question}")
        # Handle both string and list answers
        if isinstance(entry.answer, str):
            memory_lines.append(f"Assistant: {entry.answer}")
        elif isinstance(entry.answer, list) and entry.answer:
            memory_lines.append(f"Assistant: Provided data based on your query (found {len(entry.answer)} items).")
        else:
            memory_lines.append(f"Assistant: No answer recorded.")
    return "\n".join(memory_lines)

def process_question(reference_id: str, question: str) -> Tuple[str, Any, Optional[List[ErrorHistoryItem]]]:
    schema_data = parse_schema_summary(SCHEMA_DIR)
    current_timestamp = get_ist_timestamp()
    llm_memory_context = ""
    error_history_for_current_turn: Optional[List[ErrorHistoryItem]] = None

    NON_QUERY_OR_OUT_OF_SCOPE_RESPONSE = "I'm sorry, I couldn't found any result."
    
    # --- 1. Clean old conversation entries (using IST timestamp comparison) ---
    ist = tz.gettz("Asia/Kolkata")
    cutoff_datetime = datetime.now(ist) - timedelta(days=CONVERSATION_HISTORY_RETENTION_DAYS)
    cutoff_timestamp_str = cutoff_datetime.strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        # Remove entries older than cutoff
        pull_result = db[CHAT_CONVERSATIONS_COLLECTION_NAME].update_one(
            {"reference_id": reference_id},
            {"$pull": {"conversation": {"timestamp": {"$lt": cutoff_timestamp_str}}}}
        )
        if pull_result.modified_count > 0:
            logger.info(f"Removed old conversation entries (older than {CONVERSATION_HISTORY_RETENTION_DAYS} days) for reference_id '{reference_id}'.")
    except Exception as e:
        logger.error(f"Error removing old conversation entries for reference_id '{reference_id}': {e}", exc_info=True)

    # --- 2. Load Current Conversation for LLM Memory ---
    conversation_doc_dict = db[CHAT_CONVERSATIONS_COLLECTION_NAME].find_one({"reference_id": reference_id})
    all_conversation_entries_from_db: List[ConversationEntry] = []

    if conversation_doc_dict:
        try:
            loaded_conversation_doc = ChatConversationDocument.model_validate(conversation_doc_dict)
            if loaded_conversation_doc.conversation:
                 all_conversation_entries_from_db = loaded_conversation_doc.conversation
                 llm_memory_context = format_conversation_history_for_llm(all_conversation_entries_from_db)
                 logger.info(f"Loaded {len(all_conversation_entries_from_db)} entries from DB for {reference_id} (for LLM context).")
        except Exception as e:
            logger.error(f"Error validating existing conversation document for {reference_id}: {e}")

    # --- 3. Process the New Question ---
    logger.info(f"Processing question '{question}' for reference_id '{reference_id}' at {current_timestamp}")
    if is_mongo_query_request(question):
        mongo_query_str = generate_mongo_query(question, schema_data, memory=llm_memory_context)
    else:
        logger.info("ELSEEEEEEEEE")
        mongo_query_str = generate_conversation_response(question, memory=llm_memory_context)
    logger.info(f"LLM generated for '{question}': {mongo_query_str}")

    # Determine the current answer
    current_answer: Any
    
    if "db." not in mongo_query_str.strip():
        logger.info(f"LLM determined question '{question}' is out of scope or not a query.")
        current_answer = mongo_query_str.strip()
    else:
        logger.info(f"Attempting to execute MongoDB query: {mongo_query_str}")
        raw_results, error, error_history_models = execute_mongo_with_retries(
            question, mongo_query_str, schema_data
        )
        error_history_for_current_turn = error_history_models
        
        if error:
            logger.error(f"Error executing MongoDB query for '{question}': {error}")
            current_answer = f"Error executing query: {error}"
        else:
            # Flatten results for processing
            flat_data_results = []
            if raw_results:
                for query_result_group in raw_results:
                    if "results" in query_result_group and isinstance(query_result_group["results"], list):
                        flat_data_results.extend(query_result_group["results"])
            
            if not flat_data_results:
                logger.info(f"MongoDB query for '{question}' returned no documents.")
                current_answer = "Your query executed successfully but returned no matching documents."
            else:
                logger.info(f"MongoDB query for '{question}' successful, {len(flat_data_results)} items found.")
                current_answer = flat_data_results

    # --- 4. Create and Append the New Conversation Entry ---
    new_qna_entry = ConversationEntry(
        timestamp=current_timestamp,  # ✅ IST timestamp string
        question=question,
        answer=current_answer
    )

    try:
        update_result = db[CHAT_CONVERSATIONS_COLLECTION_NAME].update_one(
            {"reference_id": reference_id},
            {
                "$push": {"conversation": new_qna_entry.model_dump(exclude_none=True)},
                "$setOnInsert": {"reference_id": reference_id}
            },
            upsert=True
        )
        if update_result.upserted_id:
            logger.info(f"Created new conversation document for reference_id '{reference_id}' at {current_timestamp}")
        elif update_result.modified_count > 0:
            logger.info(f"Appended new conversation entry for reference_id '{reference_id}' at {current_timestamp}")
    except Exception as e:
        logger.error(f"Failed to append conversation entry for reference_id '{reference_id}': {e}", exc_info=True)

    return question, current_answer, error_history_for_current_turn