from pydantic import BaseModel, Field
from typing import Any, List, Optional, Dict
from datetime import datetime, timezone
from dateutil import tz
# Helper function for Zulu time formatting

def get_ist_timestamp() -> str:
    """Get current timestamp in IST format: YYYY-MM-DD HH:MM:SS"""
    ist = tz.gettz("Asia/Kolkata")
    return datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

class ChatRequest(BaseModel):
    reference_id: str
    question: str

class ErrorHistoryItem(BaseModel):
    attempt: int
    query: Optional[str] = None
    error: str
    fix: Optional[str] = None

class MongoResult(BaseModel): # This is a general model, may not be directly in ChatConversationDocument
    collection: str
    filter: Any
    projection: Any
    results: List[Any]

# This ChatResponse might be for an older structure or a different purpose.
# The primary response for the /chat endpoint is now CurrentChatInteractionResponse.
class ChatResponse(BaseModel):
    reference_id: str
    timestamp: str
    question: str
    response_type: str # e.g., 'mongo_query', 'conversation'
    response: Optional[str] = None # For direct LLM text
    mongo_query: Optional[str] = None
    results: Optional[List[MongoResult]] = None # For structured query results
    # error: Optional[str] = None
    # error_history: Optional[List[ErrorHistoryItem]] = None
    # table_output: Optional[str] = None

# --- Models for Chat Conversation Collection ---

class ConversationEntry(BaseModel):
    timestamp: str = Field(default_factory=get_ist_timestamp) # For 30-day memory filtering
    question: str
    #answer: List[Dict[str, Any]] # Flexible: holds AI text response or structured data
    answer:Any

class ChatConversationDocument(BaseModel):
    # FIXED: Don't use reference_id as _id, let MongoDB generate its own _id
    # Remove the alias to avoid mapping reference_id to _id
    reference_id: str  # This will be a separate field, not the MongoDB _id
    conversation: List[ConversationEntry] = []
    
    class Config:
        populate_by_name = True
        
# --- New Response Model for the /chat endpoint ---
class CurrentChatInteractionResponse(BaseModel):
    reference_id: str
    current_timestamp: str = Field(default_factory=get_ist_timestamp) # Timestamp for THIS specific interaction
    question: str
    #answer: List[Dict[str, Any]] # The answer to the current question
    answer:Any
    
    
    # Optional: If you want to include error history for the current attempt in the response
    #error_history: Optional[List[ErrorHistoryItem]] = None
    
    class Config:
        populate_by_name = True
       