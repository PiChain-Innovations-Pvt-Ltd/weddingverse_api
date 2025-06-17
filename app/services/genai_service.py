import json
import google.generativeai as genai
import vertexai
from vertexai.preview.generative_models import GenerativeModel, Part
from google.oauth2 import service_account
from app.config import settings
from app.utils.logger import logger
from typing import List, Dict, Any

GEMINI_API_KEY = settings.gemini_api_key

genai.configure(api_key=GEMINI_API_KEY)
try:
    credentials = service_account.Credentials.from_service_account_file(settings.CREDENTIALS_PATH)
    vertexai.init(project=settings.PROJECT_ID, location=settings.REGION, credentials=credentials)
    logger.info("Vertex AI initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize Vertex AI: {e}")
    raise RuntimeError(f"Failed to initialize Vertex AI: {e}. Application cannot proceed.")

model = GenerativeModel(
    model_name=settings.MODEL_NAME,
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

def generate_conversation_response(question: str, memory: str = "") -> str:
    prompt = f"""
    You are Wed AI, a friendly and helpful AI assistant whose sole purpose is to assist users with wedding planning.
    You are strictly limited to wedding-related topics.

    Carefully analyze the user's input and follow these rules in order:

    1.  **Handle Greetings**: If the user's input is primarily a common social greeting or pleasantry (e.g., "Hi", "Hello", "Good morning", "How are you?", "Hey there"), respond with a warm greeting and immediately offer assistance with wedding planning. For instance, you could say "Hello! How can I help you plan your wedding today?" or "Hi there! What wedding-related questions do you have for me?".

    2.  **Check Domain Relevance**: If the user's input is not a greeting and is *not related to wedding planning*, you must politely inform them that your expertise is limited to wedding planning and redirect them to ask wedding-related questions. For example: "I'm sorry, but my expertise is limited to wedding planning. How can I assist you with your wedding preparations?"

    3.  **External Links Policy**: Do not recommend or reference any external websites (e.g., booking or travel sites). If the user's question specifically requests them or would require providing such a link, respond ONLY with: "I'm sorry, I couldn't find the results."

    4.  **Answer Wedding Questions**: Otherwise, if the question is related to wedding planning and doesn't violate the external link rule, answer the question in a helpful and concise manner. This includes general conversational questions about wedding planning.
    
    User asked: "{question}"

    Memory of conversation:
    {memory}
    """
    response = model.generate_content([prompt])
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
    response = model.generate_content([combined_prompt])
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
    response = model.generate_content([prompt])
    return response.text.strip()