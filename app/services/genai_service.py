# import json
# import google.generativeai as genai
# from app.config import settings
# from typing import List, Dict, Any

# GEMINI_API_KEY = settings.gemini_api_key

# genai.configure(api_key=GEMINI_API_KEY)
# model = genai.GenerativeModel(
#     model_name="gemini-2.0-flash",
#     generation_config={"temperature": 0.5, "max_output_tokens": 4096}
# )

# def format_conversation_history(conversation_entries: List[Dict[str, Any]]) -> str:
#     """
#     Format conversation history into a string for context
#     """
#     if not conversation_entries:
#         return ""
    
#     # Get the last 5 conversation turns for context
#     recent_entries = conversation_entries[-5:]
#     formatted_history = ""
    
#     for entry in recent_entries:
#         question = entry.get("question", "")
#         answer = entry.get("answer", [])
        
#         formatted_history += f"User: {question}\n"
        
#         if answer:
#             if isinstance(answer[0], dict) and "text" in answer[0]:
#                 # This is a text response
#                 formatted_history += f"Assistant: {answer[0]['text']}\n\n"
#             else:
#                 # This is a result set
#                 formatted_history += "Assistant: [Results provided]\n\n"
    
#     return formatted_history

# def generate_conversation_response(question: str, memory: str = "") -> str:
#     prompt = f"""
#     You are a friendly wedding planning assistant.
#     Before answering, check if the user's question is related to wedding planning. 
#     If it is not, respond ONLY with: "I'm sorry, I couldn't found the results."

#     Additionally, do not recommend or reference any external websites (e.g., booking or travel sites). 
#     If the user's question specifically requests them or would require providing such a link, respond ONLY with:
#     "I'm sorry, I couldn't found the results."

#     Otherwise, answer the following question in a helpful and concise manner:

#     User asked: "{question}"

#     Memory of conversation:
#     {memory}
#     """
#     response = model.generate_content(prompt)
#     return response.text.strip()

# def generate_mongo_query(question: str, schema_data: dict, memory: str = "") -> str:
#     schema_context = ""
#     for collection, info in schema_data.items():
#         schema_context += f"Collection: {collection}\nDescription: {info['description']}\nFields:\n"
#         for field in info["fields"]:
#             schema_context += f"- {field['name']} ({field['type']}): {field['description']}\n"
#         schema_context += "\n"
#     combined_prompt = f"""
#     You are a combined wedding planning assistant. Before generating any output, check if the user's question is about wedding planning.
#     If the question is not wedding related, respond ONLY with:
#     "I'm sorry, I couldn't found any result."
#     Otherwise, proceed as follows:

#     1. When a user asks for a MongoDB query, you must convert their natural language description into valid MongoDB find() queries.
#     Sometimes a single question may need multiple queries (e.g., if the user wants results from multiple collections such as "venue and photographer"). 
#     In that case, respond ONLY with multiple lines, each in the format:
#         db.<collection>.find({{ <filter> }}, {{ <projection> }}).limit(10)
#     No extra text or explanation—just the queries.

#     Make sure to produce one query per relevant collection if multiple items are requested.
#     Follow these rules for query conversion:
#     - Based on the user's query, select the top 3 data fields from the relevant collection that best answer the question.
#     - In the projection, ALWAYS include the following location fields: "City", "PinCode", and "State".
#     - Return only 10 records per query using the .limit(10) clause.
#     - Use the exact field names as defined in the wedding planning schema.
#     - Handle price conversions (e.g., "Lakhs" → 100000) if mentioned.
#     - Use proper MongoDB operators like "$lt", "$gte", "$in", etc.
#     - Support nested fields with dot notation if needed.
#     - Format the query in valid JSON with double quotes only and no trailing commas.
#     - Use numerical values without quotes (e.g., 50000 not "50000").

#     2. Otherwise, if the user's input is not a request for a MongoDB query but is instead a conversational query about wedding planning, answer the question in a friendly, helpful manner.

#     Remember:
#     - When generating a MongoDB query, output ONLY the query (or queries) in the required format, with each query on a new line if there are multiple.
#     - Do NOT combine multiple items into a single query if they belong to different collections.
#     - Consider the conversation history when interpreting the question, especially for follow-up questions.

#     WEDDING PLANNING SCHEMA:
#     {schema_context}

#     User question:
#     {question}

#     Memory of conversation:
#     {memory}
#     """
#     response = model.generate_content(combined_prompt)
#     return response.text.strip().removeprefix("```").removesuffix("```").strip()


# def fix_mongo_query(question: str, mongo_query: str, error_message: str, schema_data: dict) -> str:
#     schema_context = ""
#     for collection, info in schema_data.items():
#         schema_context += f"Collection: {collection}\nDescription: {info['description']}\nFields:\n"
#         for field in info["fields"]:
#             schema_context += f"- {field['name']} ({field['type']}): {field['description']}\n"
#         schema_context += "\n"
#     prompt = f"""
#     You are a MongoDB expert specializing in wedding planning data.
#     The following MongoDB query (or queries) generated an error when executed.

#     ORIGINAL QUESTION:
#     {question}

#     ORIGINAL QUERY:
#     {mongo_query}

#     ERROR MESSAGE:
#     {error_message}

#     Using the wedding planning schema below:
#     {schema_context}

#     Please fix the query (or queries) to correctly use the right collection and field names, handle price conversions, 
#     and follow the correct syntax.
#     Respond ONLY with the fixed queries, each in the format:
#     db.<collection>.find({{ ... }}, {{ ... }}).limit(10)
#     """
#     response = model.generate_content(prompt)
#     return response.text.strip()

# def generate_table_from_results(question: str, all_results: list) -> str:
#     results_json = json.dumps(all_results, indent=2)
#     prompt = f"""
#     You are a helpful wedding planning assistant. The user asked: "{question}"

#     Below is a JSON representation of the MongoDB query results for each collection:
#     {results_json}

#     You must strictly follow these instructions:

#     1. First, count the total number of documents returned across all collections. Let's call this total "N".
#     2. If N is 2 or fewer, DO NOT produce a table. 
#     - Instead, produce a short, direct, human-friendly summary describing the relevant fields in each document.
#     3. If N is more than 2, produce a neat table or tables in Markdown format (| col1 | col2 | ... |).
#     - Precede the table with a heading that is the collection name followed by a colon (e.g. "Venues:").
#     - If multiple collections appear, produce multiple tables (one per collection).
#     - If a collection has no results, say "No results found" for that collection.
#     4. Before producing your final answer, confirm that the user's query is wedding-related. If not, respond ONLY with:
#     "I'm sorry, I couldn't found any results."
#     5. Output only your final answer—no extra commentary, disclaimers, or reasoning steps.

#     IMPORTANT: Do not deviate from these instructions. If N ≤ 2, absolutely do not use tables.
#     """
#     response = model.generate_content(prompt)
#     return response.text.strip()







import json
import google.generativeai as genai
from app.config import settings
from typing import List, Dict, Any, Optional
from app.utils.logger import logger  # Add this import

GEMINI_API_KEY = settings.gemini_api_key

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    generation_config={"temperature": 0.5, "max_output_tokens": 4096}
)

def format_conversation_history(conversation_entries: List[Dict[str, Any]]) -> str:
    """
    Format conversation history into a string for context
    """
    if not conversation_entries:
        return ""
    
    # Get the last 5 conversation turns for context
    recent_entries = conversation_entries[-5:]
    formatted_history = ""
    
    for entry in recent_entries:
        question = entry.get("question", "")
        answer = entry.get("answer", [])
        
        formatted_history += f"User: {question}\n"
        
        if answer:
            if isinstance(answer[0], dict) and "text" in answer[0]:
                # This is a text response
                formatted_history += f"Assistant: {answer[0]['text']}\n\n"
            else:
                # This is a result set
                formatted_history += "Assistant: [Results provided]\n\n"
    
    return formatted_history

def check_similar_question_in_memory(current_question: str, memory: str) -> Optional[str]:
    """
    Clean semantic similarity check with professor-level analysis (no syntax issues)
    """
    if not memory or not memory.strip():
        return None
    
    prompt = f"""
    You are a distinguished Professor of Computational Linguistics specializing in semantic analysis and wedding planning domain language.

    CURRENT QUESTION: "{current_question}"

    CONVERSATION HISTORY:
    {memory}

    EXPERT SEMANTIC ANALYSIS TASK:

    WEDDING DOMAIN SEMANTIC KNOWLEDGE:
    
    Venue Terms: venue, hall, location, place, spot, site, facility, space, center, complex, resort, hotel, banquet, auditorium, marriage hall, function hall, wedding venue, reception venue, ceremony venue
    
    Photography Terms: photographer, photography, photo, picture, camera, shoot, candid, traditional, pre-wedding, wedding photography service, photo coverage, video coverage, cinematography
    
    Catering Terms: caterer, catering, food, menu, cuisine, buffet, meal, dining, refreshment, catering service, food service, wedding catering
    
    Budget Terms: cost, price, budget, rate, charge, fee, amount, expense, affordable, cheap, expensive, premium, under, below, within, above, less than, more than
    
    Location Terms: in, at, around, near, within, area, city, locality, region, zone
    
    Quality Terms: good, best, top, excellent, quality, premium, recommended, popular, famous, experienced, professional

    ADVANCED LINGUISTIC ANALYSIS:

    1. SEMANTIC EQUIVALENCE PATTERNS:
    - "Show me X" = "Find X" = "List X" = "Give me X" = "Provide X"
    - "venues" = "halls" = "wedding locations" = "marriage halls" = "function halls"
    - "photographers" = "photography services" = "photo coverage" = "camera services"
    - "under 50k" = "below 50000" = "within 50k budget" = "less than fifty thousand"
    - "in Mumbai" = "Mumbai area" = "around Mumbai" = "Mumbai city" = "Mumbai region"
    - "good caterers" = "quality catering" = "best catering services" = "recommended caterers"

    2. NUMERICAL UNDERSTANDING:
    - 1 lakh = 100000 = 1L = one lakh
    - 50k = 50000 = fifty thousand
    - 2 lakhs = 200000 = 2L = two lakhs

    3. IMPLICIT CONTEXT EXPANSION:
    - In wedding planning context: "venues" means "wedding venues"
    - In wedding planning context: "photographers" means "wedding photographers"
    - In wedding planning context: "caterers" means "wedding caterers"

    4. FUNCTIONAL EQUIVALENCE TEST:
    Ask: "Would the answer to the previous question completely satisfy the current question's information need?"

    SIMILARITY EXAMPLES:

    HIGH SIMILARITY (Should Match):
    ✓ "Show me venues in Mumbai" ↔ "Find wedding halls in Mumbai"
    ✓ "List photographers under 50000" ↔ "Photography services within 50k budget"  
    ✓ "Good caterers in Delhi" ↔ "Quality catering services Delhi area"
    ✓ "Budget venues under 1 lakh" ↔ "Affordable wedding halls below 100000"
    ✓ "Venues with parking" ↔ "Wedding halls that have parking facilities"

    NO SIMILARITY (Should NOT Match):
    ✗ "Venues in Mumbai" ↔ "Photographers in Mumbai" (different services)
    ✗ "Under 1 lakh venues" ↔ "Above 2 lakh venues" (opposite budget ranges)
    ✗ "Mumbai venues" ↔ "Delhi venues" (different locations)
    ✗ "Indoor venues" ↔ "Outdoor venues" (opposite venue types)

    ANALYSIS INSTRUCTION:
    Using your expertise in computational linguistics, analyze if the current question is semantically equivalent to ANY previous question in the conversation history. Look beyond surface words to deep meaning, intent, and functional equivalence.

    Consider:
    - Synonym relationships and paraphrasing
    - Domain-specific terminology variations
    - Implicit context and assumptions
    - Pragmatic intent and information goals
    - Numerical and measurement equivalencies

    RESPONSE FORMAT:
    If you find a semantically equivalent question: "SIMILAR: [exact previous question text]"
    If no equivalent question exists: "NOT_SIMILAR"

    Your analysis should demonstrate the rigor of advanced linguistic research.

    RESULT:
    """
    
    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        if response_text.startswith("SIMILAR:"):
            similar_question = response_text.replace("SIMILAR:", "").strip()
            logger.info(f"Semantic match found: '{current_question}' ↔ '{similar_question}'")
            return similar_question
        else:
            logger.debug(f"No semantic match for: '{current_question}'")
            return None
            
    except Exception as e:
        #logger.warning(f"Error in semantic similarity check: {e}")
        return None

def generate_conversation_response(question: str, memory: str = "") -> str:
    prompt = f"""
    You are a friendly wedding planning assistant.
    Before answering, check if the user's question is related to wedding planning. 
    If it is not, respond ONLY with: "I'm sorry, I couldn't found the results."

    Additionally, do not recommend or reference any external websites (e.g., booking or travel sites). 
    If the user's question specifically requests them or would require providing such a link, respond ONLY with:
    "I'm sorry, I couldn't found the results."

    Otherwise, answer the following question in a helpful and concise manner:

    User asked: "{question}"

    Memory of conversation:
    {memory}
    """
    response = model.generate_content(prompt)
    return response.text.strip()

def generate_mongo_query(question: str, schema_data: dict, memory: str = "") -> str:
    schema_context = ""
    for collection, info in schema_data.items():
        schema_context += f"Collection: {collection}\nDescription: {info['description']}\nFields:\n"
        for field in info["fields"]:
            schema_context += f"- {field['name']} ({field['type']}): {field['description']}\n"
        schema_context += "\n"
    combined_prompt = f"""
    You are a combined wedding planning assistant. Before generating any output, check if the user's question is about wedding planning.
    If the question is not wedding related, respond ONLY with:
    "I'm sorry, I couldn't found any result."
    Otherwise, proceed as follows:

    1. When a user asks for a MongoDB query, you must convert their natural language description into valid MongoDB find() queries.
    Sometimes a single question may need multiple queries (e.g., if the user wants results from multiple collections such as "venue and photographer"). 
    In that case, respond ONLY with multiple lines, each in the format:
        db.<collection>.find({{ <filter> }}, {{ <projection> }}).limit(10)
    No extra text or explanation—just the queries.

    Make sure to produce one query per relevant collection if multiple items are requested.
    Follow these rules for query conversion:
    - Based on the user's query, select the top 3 data fields from the relevant collection that best answer the question.
    - In the projection, ALWAYS include the following location fields: "City", "PinCode", and "State".
    - Return only 10 records per query using the .limit(10) clause.
    - Use the exact field names as defined in the wedding planning schema.
    - Handle price conversions (e.g., "Lakhs" → 100000) if mentioned.
    - Use proper MongoDB operators like "$lt", "$gte", "$in", etc.
    - Support nested fields with dot notation if needed.
    - Format the query in valid JSON with double quotes only and no trailing commas.
    - Use numerical values without quotes (e.g., 50000 not "50000").

    2. Otherwise, if the user's input is not a request for a MongoDB query but is instead a conversational query about wedding planning, answer the question in a friendly, helpful manner.

    Remember:
    - When generating a MongoDB query, output ONLY the query (or queries) in the required format, with each query on a new line if there are multiple.
    - Do NOT combine multiple items into a single query if they belong to different collections.
    - Consider the conversation history when interpreting the question, especially for follow-up questions.

    WEDDING PLANNING SCHEMA:
    {schema_context}

    User question:
    {question}

    Memory of conversation:
    {memory}
    """
    response = model.generate_content(combined_prompt)
    return response.text.strip().removeprefix("```").removesuffix("```").strip()

def fix_mongo_query(question: str, mongo_query: str, error_message: str, schema_data: dict) -> str:
    schema_context = ""
    for collection, info in schema_data.items():
        schema_context += f"Collection: {collection}\nDescription: {info['description']}\nFields:\n"
        for field in info["fields"]:
            schema_context += f"- {field['name']} ({field['type']}): {field['description']}\n"
        schema_context += "\n"
    prompt = f"""
    You are a MongoDB expert specializing in wedding planning data.
    The following MongoDB query (or queries) generated an error when executed.

    ORIGINAL QUESTION:
    {question}

    ORIGINAL QUERY:
    {mongo_query}

    ERROR MESSAGE:
    {error_message}

    Using the wedding planning schema below:
    {schema_context}

    Please fix the query (or queries) to correctly use the right collection and field names, handle price conversions, 
    and follow the correct syntax.
    Respond ONLY with the fixed queries, each in the format:
    db.<collection>.find({{ ... }}, {{ ... }}).limit(10)
    """
    response = model.generate_content(prompt)
    return response.text.strip()

def generate_table_from_results(question: str, all_results: list) -> str:
    results_json = json.dumps(all_results, indent=2)
    prompt = f"""
    You are a helpful wedding planning assistant. The user asked: "{question}"

    Below is a JSON representation of the MongoDB query results for each collection:
    {results_json}

    You must strictly follow these instructions:

    1. First, count the total number of documents returned across all collections. Let's call this total "N".
    2. If N is 2 or fewer, DO NOT produce a table. 
    - Instead, produce a short, direct, human-friendly summary describing the relevant fields in each document.
    3. If N is more than 2, produce a neat table or tables in Markdown format (| col1 | col2 | ... |).
    - Precede the table with a heading that is the collection name followed by a colon (e.g. "Venues:").
    - If multiple collections appear, produce multiple tables (one per collection).
    - If a collection has no results, say "No results found" for that collection.
    4. Before producing your final answer, confirm that the user's query is wedding-related. If not, respond ONLY with:
    "I'm sorry, I couldn't found any results."
    5. Output only your final answer—no extra commentary, disclaimers, or reasoning steps.

    IMPORTANT: Do not deviate from these instructions. If N ≤ 2, absolutely do not use tables.
    """
    response = model.generate_content(prompt)
    return response.text.strip()