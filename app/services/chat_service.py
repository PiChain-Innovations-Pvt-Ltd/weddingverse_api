# app/services/chat_service.py
import json
import re
from datetime import datetime, timezone, timedelta
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

SCHEMA_DIR = settings.schema_dir
CHAT_CONVERSATIONS_COLLECTION_NAME = settings.CHAT_CONVERSATIONS_COLLECTION
CONVERSATION_HISTORY_RETENTION_DAYS = 30

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

def format_query_results_as_text(raw_results: List[Dict[str, Any]]) -> str:
    """Convert query results to a readable text format for frontend"""
    if not raw_results:
        return "No data found."
    
    formatted_parts = []
    total_items = 0
    
    for query_result in raw_results:
        collection = query_result.get("collection", "unknown")
        results = query_result.get("results", [])
        
        if results:
            total_items += len(results)
            formatted_parts.append(f"Found {len(results)} items in {collection}:")
            
            for i, item in enumerate(results[:5], 1):  # Show first 5 items
                formatted_parts.append(f"{i}. {json.dumps(item, indent=2)}")
            
            if len(results) > 5:
                formatted_parts.append(f"... and {len(results) - 5} more items")
        else:
            formatted_parts.append(f"No items found in {collection}")
    
    if total_items == 0:
        return "Your query executed successfully but returned no matching documents."
    
    return "\n".join(formatted_parts)

# Updated return type to handle both cases
def process_question(reference_id: str, question: str) -> Tuple[str, Any, Optional[List[ErrorHistoryItem]]]:
    schema_data = parse_schema_summary(SCHEMA_DIR)
    now_utc = datetime.now(timezone.utc)
    llm_memory_context = ""
    error_history_for_current_turn: Optional[List[ErrorHistoryItem]] = None

    NON_QUERY_OR_OUT_OF_SCOPE_RESPONSE = "I'm sorry, I couldn't found any result."
    
    # --- 1. Delete Old Conversation Entries from Database ---
    cutoff_date = now_utc - timedelta(days=CONVERSATION_HISTORY_RETENTION_DAYS)
    try:
        pull_result = db[CHAT_CONVERSATIONS_COLLECTION_NAME].update_one(
            {"reference_id": reference_id},  # Query by reference_id field, not _id
            {"$pull": {"conversation": {"timestamp": {"$lt": cutoff_date}}}}
        )
        if pull_result.modified_count > 0:
            logger.info(f"Removed {pull_result.modified_count} old conversation entries (older than {CONVERSATION_HISTORY_RETENTION_DAYS} days) for reference_id '{reference_id}'.")
    except Exception as e:
        logger.error(f"Error removing old conversation entries for reference_id '{reference_id}': {e}", exc_info=True)

    # --- 2. Load Current Conversation for LLM Memory ---
    conversation_doc_dict = db[CHAT_CONVERSATIONS_COLLECTION_NAME].find_one({"reference_id": reference_id})  # Query by reference_id field
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
    logger.info(f"Processing question '{question}' for reference_id '{reference_id}'.")
    mongo_query_str = generate_mongo_query(question, schema_data, memory=llm_memory_context)
    logger.info(f"LLM generated for '{question}': {mongo_query_str}")

    # Determine the current answer
    current_answer: Any  # Can be string or list
    
    if mongo_query_str.strip() == NON_QUERY_OR_OUT_OF_SCOPE_RESPONSE:
        logger.info(f"LLM determined question '{question}' is out of scope or not a query.")
        current_answer = NON_QUERY_OR_OUT_OF_SCOPE_RESPONSE  # Simple string for out-of-scope
    else:
        logger.info(f"Attempting to execute MongoDB query: {mongo_query_str}")
        raw_results, error, error_history_models = execute_mongo_with_retries(
            question, mongo_query_str, schema_data
        )
        error_history_for_current_turn = error_history_models
        
        if error:
            logger.error(f"Error executing MongoDB query for '{question}': {error}")
            current_answer = f"Error executing query: {error}"  # Simple string for errors
        else:
            # Flatten results for processing
            flat_data_results = []
            if raw_results:
                for query_result_group in raw_results:
                    if "results" in query_result_group and isinstance(query_result_group["results"], list):
                        flat_data_results.extend(query_result_group["results"])
            
            if not flat_data_results:
                logger.info(f"MongoDB query for '{question}' returned no documents.")
                current_answer = "Your query executed successfully but returned no matching documents."  # Simple string for no data
            else:
                logger.info(f"MongoDB query for '{question}' successful, {len(flat_data_results)} items found.")
                current_answer = flat_data_results  # List of dictionaries for actual data

    # --- 4. Create and Append the New Conversation Entry to the Database ---
    new_qna_entry = ConversationEntry(
        question=question,
        answer=current_answer
    )

    try:
        # FIXED: Let MongoDB generate its own _id, don't use reference_id as _id
        update_result = db[CHAT_CONVERSATIONS_COLLECTION_NAME].update_one(
            {"reference_id": reference_id},  # Query by reference_id field
            {
                "$push": {"conversation": new_qna_entry.model_dump(exclude_none=True)},
                "$setOnInsert": {"reference_id": reference_id}  # Only set reference_id field, let _id be auto-generated
            },
            upsert=True
        )
        if update_result.upserted_id:
            logger.info(f"Created new conversation document with MongoDB _id '{update_result.upserted_id}' for reference_id '{reference_id}'.")
        elif update_result.modified_count > 0:
            logger.info(f"Appended new conversation entry for reference_id '{reference_id}'.")
    except Exception as e:
        logger.error(f"Failed to append conversation entry for reference_id '{reference_id}': {e}", exc_info=True)

    return question, current_answer, error_history_for_current_turn   




########### NO DB delete ############################

# # app/services/chat_service.py
# import json
# import re
# from datetime import datetime, timezone, timedelta
# from typing import List, Dict, Any, Optional, Tuple
# from app.services.mongo_service import db
# from app.services.genai_service import (
#     generate_conversation_response,
#     generate_mongo_query,
#     fix_mongo_query,
# )
# from app.utils.schema_parser import parse_schema_summary
# from app.utils.logger import logger
# from app.config import settings
# from app.models.chat import ConversationEntry, ChatConversationDocument, ErrorHistoryItem

# SCHEMA_DIR = settings.schema_dir
# CHAT_CONVERSATIONS_COLLECTION_NAME = settings.CHAT_CONVERSATIONS_COLLECTION
# CONVERSATION_HISTORY_RETENTION_DAYS = 30
# LLM_CONTEXT_DAYS = 30  # New parameter for LLM context window

# def is_mongo_query_request(question: str) -> bool:
#     keywords = ["find", "show", "list", "where", "query", "give", "provide"]
#     return any(kw in question.lower() for kw in keywords)

# def find_matching_parenthesis(s: str, start: int) -> int:
#     paren = 0
#     for i in range(start, len(s)):
#         if s[i] == "(":
#             paren += 1
#         elif s[i] == ")":
#             if paren == 0:
#                 return i
#             paren -= 1
#     return -1

# def split_filter_projection(args_str: str):
#     if ',' not in args_str:
#         return args_str, ""
#     brace_level = 0
#     boundary = -1
#     for i, ch in enumerate(args_str):
#         if ch == "{":
#             brace_level += 1
#         elif ch == "}":
#             brace_level -= 1
#             if brace_level == 0:
#                 boundary = i
#                 break
#     if boundary == -1:
#         return args_str, ""
#     filter_part = args_str[:boundary+1].strip()
#     remainder = args_str[boundary+1:].strip()
#     if remainder.startswith(','):
#         remainder = remainder[1:].strip()
#     return filter_part, remainder

# def execute_mongo_queries(query_string: str):
#     pattern = r"(db\.[a-zA-Z0-9_]+\.find\s*\((.*?)\)(?:\.limit\s*\(\s*(\d+)\s*\))?)"
#     matches = re.findall(pattern, query_string, flags=re.DOTALL)

#     if not matches:
#         if query_string.startswith("db.") and ".find(" in query_string:
#             try:
#                 coll_part = query_string.split(".find(")[0].replace("db.", "")
#                 args_part_full = query_string.split(".find(")[1]
#                 limit_val_simple = 10
#                 limit_match_simple = re.search(r"\)\.limit\s*\(\s*(\d+)\s*\)$", args_part_full)
#                 if limit_match_simple:
#                     limit_val_simple = int(limit_match_simple.group(1))
#                     args_part_full = args_part_full[:limit_match_simple.start()]
#                 if not args_part_full.endswith(")"):
#                     return None, "Malformed find() arguments in simple parse."
#                 args_part = args_part_full[:-1]
#                 matches = [(query_string, args_part, str(limit_val_simple) if limit_match_simple else "")]
#             except Exception as e:
#                 logger.error(f"Simple query parse error: {e} for query: {query_string}")
#                 return None, "Invalid query format for simple parsing."
#         else:
#             logger.warning(f"No valid MongoDB query found in string: {query_string}")
#             return None, "Invalid query format or no queries found matching pattern."

#     all_query_results = []
#     for full_match_str, inner_args_str, limit_str in matches:
#         m_coll = re.match(r"db\.([^.]+)\.find", full_match_str.strip())
#         if not m_coll:
#             return None, f"Could not extract collection from {full_match_str}"
#         coll_name = m_coll.group(1)
#         filt_str, proj_str = split_filter_projection(inner_args_str.strip())
#         try:
#             filt = json.loads(filt_str) if filt_str else {}
#         except Exception as e:
#             logger.error(f"Error parsing filter '{filt_str}': {e}")
#             return None, f"Error parsing filter '{filt_str}': {e}"
#         proj = None
#         if proj_str:
#             try:
#                 proj = json.loads(proj_str)
#             except Exception as e:
#                 logger.error(f"Error parsing projection '{proj_str}': {e}")
#                 return None, f"Error parsing projection '{proj_str}': {e}"
#         limit_val = int(limit_str) if limit_str and limit_str.isdigit() else 10
#         try:
#             cursor = db[coll_name].find(filt, proj).limit(limit_val)
#             results_list = list(cursor)
#             for doc in results_list:
#                 if "_id" in doc:
#                     doc.pop("_id", None)
#         except Exception as e:
#             logger.error(f"MongoDB execution error for collection '{coll_name}': {e}")
#             return None, f"MongoDB execution error for collection '{coll_name}': {e}"
#         all_query_results.append({"collection": coll_name, "filter": filt, "projection": proj, "results": results_list})
#     return all_query_results, None

# def execute_mongo_with_retries(question: str, query_string: str, schema_data: dict, max_retries=3):
#     attempts = 0
#     error_history_list_of_dicts: List[Dict[str, Any]] = []
#     current_query_string = query_string
#     while attempts < max_retries:
#         results, error = execute_mongo_queries(current_query_string)
#         if error:
#             attempts += 1
#             error_item_dict: Dict[str, Any] = {"attempt": attempts, "query": current_query_string, "error": str(error)}
#             error_history_list_of_dicts.append(error_item_dict)
#             logger.info(f"Attempt {attempts} failed for query: {current_query_string}. Error: {error}")
#             fixed_query_string = fix_mongo_query(question, current_query_string, str(error), schema_data)
#             if fixed_query_string and fixed_query_string.strip() and fixed_query_string.lower() != "i'm sorry, i couldn't found any result." and fixed_query_string != current_query_string :
#                 logger.info(f"Fix suggested: {fixed_query_string}")
#                 error_history_list_of_dicts[-1]["fix"] = fixed_query_string
#                 current_query_string = fixed_query_string
#             else:
#                 logger.warning(f"No fix suggested or fix was same/invalid for: {current_query_string}")
#                 break
#         else:
#             error_history_models = [ErrorHistoryItem(**item) for item in error_history_list_of_dicts]
#             return results, None, error_history_models
#     final_error_message = error_history_list_of_dicts[-1]["error"] if error_history_list_of_dicts else "Failed to execute MongoDB query after multiple attempts."
#     error_history_models = [ErrorHistoryItem(**item) for item in error_history_list_of_dicts]
#     return None, final_error_message, error_history_models

# def format_conversation_history_for_llm(
#     conversation_entries: List[ConversationEntry],
#     context_days: int = LLM_CONTEXT_DAYS
# ) -> str:
#     """Format conversation history for LLM context using time-based filtering instead of turn count"""
#     if not conversation_entries:
#         return ""
    
#     # Calculate cutoff date for LLM context
#     now_utc = datetime.now(timezone.utc)
#     context_cutoff_date = now_utc - timedelta(days=context_days)
    
#     # Filter entries within the context window
#     context_entries = [
#         entry for entry in conversation_entries 
#         if entry.timestamp >= context_cutoff_date
#     ]
    
#     if not context_entries:
#         return ""
    
#     # Sort by timestamp to ensure chronological order
#     context_entries.sort(key=lambda x: x.timestamp)
    
#     memory_lines = []
#     for entry in context_entries:
#         memory_lines.append(f"User: {entry.question}")
#         # Handle both string and list answers
#         if isinstance(entry.answer, str):
#             memory_lines.append(f"Assistant: {entry.answer}")
#         elif isinstance(entry.answer, list) and entry.answer:
#             memory_lines.append(f"Assistant: Provided data based on your query (found {len(entry.answer)} items).")
#         else:
#             memory_lines.append(f"Assistant: No answer recorded.")
    
#     logger.info(f"Using {len(context_entries)} conversation entries from last {context_days} days for LLM context.")
#     return "\n".join(memory_lines)

# def format_query_results_as_text(raw_results: List[Dict[str, Any]]) -> str:
#     """Convert query results to a readable text format for frontend"""
#     if not raw_results:
#         return "No data found."
    
#     formatted_parts = []
#     total_items = 0
    
#     for query_result in raw_results:
#         collection = query_result.get("collection", "unknown")
#         results = query_result.get("results", [])
        
#         if results:
#             total_items += len(results)
#             formatted_parts.append(f"Found {len(results)} items in {collection}:")
            
#             for i, item in enumerate(results[:5], 1):  # Show first 5 items
#                 formatted_parts.append(f"{i}. {json.dumps(item, indent=2)}")
            
#             if len(results) > 5:
#                 formatted_parts.append(f"... and {len(results) - 5} more items")
#         else:
#             formatted_parts.append(f"No items found in {collection}")
    
#     if total_items == 0:
#         return "Your query executed successfully but returned no matching documents."
    
#     return "\n".join(formatted_parts)

# # Updated return type to handle both cases
# def process_question(reference_id: str, question: str) -> Tuple[str, Any, Optional[List[ErrorHistoryItem]]]:
#     schema_data = parse_schema_summary(SCHEMA_DIR)
#     now_utc = datetime.now(timezone.utc)
#     llm_memory_context = ""
#     error_history_for_current_turn: Optional[List[ErrorHistoryItem]] = None

#     NON_QUERY_OR_OUT_OF_SCOPE_RESPONSE = "I'm sorry, I couldn't found any result."
    
#     # --- 1. REMOVED: Database cleanup section ---
#     # We no longer delete old conversation entries from the database
#     # All conversations are kept permanently for potential future reference
    
#     # --- 2. Load Current Conversation for LLM Memory (30 days worth) ---
#     conversation_doc_dict = db[CHAT_CONVERSATIONS_COLLECTION_NAME].find_one({"reference_id": reference_id})
#     all_conversation_entries_from_db: List[ConversationEntry] = []

#     if conversation_doc_dict:
#         try:
#             loaded_conversation_doc = ChatConversationDocument.model_validate(conversation_doc_dict)
#             if loaded_conversation_doc.conversation:
#                  all_conversation_entries_from_db = loaded_conversation_doc.conversation
#                  # Updated to use time-based filtering for LLM context
#                  llm_memory_context = format_conversation_history_for_llm(all_conversation_entries_from_db)
#                  logger.info(f"Loaded {len(all_conversation_entries_from_db)} total entries from DB for {reference_id}.")
#         except Exception as e:
#             logger.error(f"Error validating existing conversation document for {reference_id}: {e}")

#     # --- 3. Process the New Question ---
#     logger.info(f"Processing question '{question}' for reference_id '{reference_id}'.")
#     mongo_query_str = generate_mongo_query(question, schema_data, memory=llm_memory_context)
#     logger.info(f"LLM generated for '{question}': {mongo_query_str}")

#     # Determine the current answer
#     current_answer: Any  # Can be string or list
    
#     if mongo_query_str.strip() == NON_QUERY_OR_OUT_OF_SCOPE_RESPONSE:
#         logger.info(f"LLM determined question '{question}' is out of scope or not a query.")
#         current_answer = NON_QUERY_OR_OUT_OF_SCOPE_RESPONSE  # Simple string for out-of-scope
#     else:
#         logger.info(f"Attempting to execute MongoDB query: {mongo_query_str}")
#         raw_results, error, error_history_models = execute_mongo_with_retries(
#             question, mongo_query_str, schema_data
#         )
#         error_history_for_current_turn = error_history_models
        
#         if error:
#             logger.error(f"Error executing MongoDB query for '{question}': {error}")
#             current_answer = f"Error executing query: {error}"  # Simple string for errors
#         else:
#             # Flatten results for processing
#             flat_data_results = []
#             if raw_results:
#                 for query_result_group in raw_results:
#                     if "results" in query_result_group and isinstance(query_result_group["results"], list):
#                         flat_data_results.extend(query_result_group["results"])
            
#             if not flat_data_results:
#                 logger.info(f"MongoDB query for '{question}' returned no documents.")
#                 current_answer = "Your query executed successfully but returned no matching documents."  # Simple string for no data
#             else:
#                 logger.info(f"MongoDB query for '{question}' successful, {len(flat_data_results)} items found.")
#                 current_answer = flat_data_results  # List of dictionaries for actual data

#     # --- 4. Create and Append the New Conversation Entry to the Database ---
#     new_qna_entry = ConversationEntry(
#         question=question,
#         answer=current_answer
#     )

#     try:
#         # Store all conversations permanently in the database
#         update_result = db[CHAT_CONVERSATIONS_COLLECTION_NAME].update_one(
#             {"reference_id": reference_id},  # Query by reference_id field
#             {
#                 "$push": {"conversation": new_qna_entry.model_dump(exclude_none=True)},
#                 "$setOnInsert": {"reference_id": reference_id}  # Only set reference_id field, let _id be auto-generated
#             },
#             upsert=True
#         )
#         if update_result.upserted_id:
#             logger.info(f"Created new conversation document with MongoDB _id '{update_result.upserted_id}' for reference_id '{reference_id}'.")
#         elif update_result.modified_count > 0:
#             logger.info(f"Appended new conversation entry for reference_id '{reference_id}'.")
#     except Exception as e:
#         logger.error(f"Failed to append conversation entry for reference_id '{reference_id}': {e}", exc_info=True)

#     return question, current_answer, error_history_for_current_turn