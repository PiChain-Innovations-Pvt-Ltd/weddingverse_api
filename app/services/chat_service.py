import re
import json
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from app.services.mongo_service import db
from app.services.genai_service import (
    generate_conversation_response,
    generate_mongo_query,
    fix_mongo_query,
    generate_table_from_results
)
from app.utils.schema_parser import parse_schema_summary
from app.config import settings

SCHEMA_DIR = settings.schema_dir
OUTPUT_COLLECTION = settings.output_collection

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
    pattern = r"(db\.[^.]+\.find\s*\(.*?\)\.limit\(\d+\))"
    matches = re.findall(pattern, query_string, flags=re.DOTALL)
    if not matches:
        return None, "Invalid query format"
    all_results = []
    for match in matches:
        m_coll = re.match(r"db\.([^.]+)\.find", match.strip())
        if not m_coll:
            return None, f"Could not extract collection from {match}"
        coll_name = m_coll.group(1)
        start = match.index("find(") + len("find(")
        end = find_matching_parenthesis(match, start)
        inner_args = match[start:end].strip()
        filt_str, proj_str = split_filter_projection(inner_args)
        try:
            filt = json.loads(filt_str)
        except Exception as e:
            return None, f"Error parsing filter: {e}"
        proj = None
        if proj_str:
            try:
                proj = json.loads(proj_str)
            except Exception as e:
                return None, f"Error parsing projection: {e}"
        cursor = db[coll_name].find(filt, proj).limit(10)
        results = list(cursor)
        # for doc in results:
        #     doc["_id"] = str(doc["_id"])
        all_results.append({
            "collection": coll_name,
            "filter": filt,
            "projection": proj,
            "results": results
        })
    return all_results, None

def execute_mongo_with_retries(question: str, query_string: str, schema_data: dict, max_retries=3):
    attempts = 0
    error_history = []
    current = query_string
    while attempts < max_retries:
        results, error = execute_mongo_queries(current)
        if error:
            attempts += 1
            error_history.append({"attempt": attempts, "query": current, "error": error})
            fixed = fix_mongo_query(question, current, error, schema_data)
            if fixed and fixed != current:
                error_history[-1]["fix"] = fixed
                current = fixed
            else:
                break
        else:
            return results, None, error_history
    return None, f"Error after {attempts} attempts", error_history

def process_question(question: str) -> dict:
    ref_id = str(uuid.uuid4())
    ist = ZoneInfo("Asia/Kolkata")
    timestamp = datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S %Z%z")
    schema_data = parse_schema_summary(SCHEMA_DIR)
    if is_mongo_query_request(question):
        mongo_query = generate_mongo_query(question, schema_data)
        results, error, error_history = execute_mongo_with_retries(question, mongo_query, schema_data)
        table_output = None
        if results and not error:
            table_output = generate_table_from_results(question, results)
        output_doc = {
            "reference_id": ref_id,
            "timestamp": timestamp,
            "question": question,
            "response_type": "mongo_query",
            "mongo_query": mongo_query,
            "results": results,
            "error": error,
            "error_history": error_history,
            "table_output": table_output
        }
    else:
        resp = generate_conversation_response(question)
        output_doc = {
            "reference_id": ref_id,
            "timestamp": timestamp,
            "question": question,
            "response_type": "conversation",
            "response": resp
        }
    db[OUTPUT_COLLECTION].insert_one(output_doc)
    return output_doc
