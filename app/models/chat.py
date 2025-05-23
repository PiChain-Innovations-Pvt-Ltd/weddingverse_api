from pydantic import BaseModel, Field
from typing import Any, List, Optional, Dict
from datetime import datetime, timezone

# Helper function for Zulu time formatting
def datetime_to_zulu(dt: datetime) -> str:
    if dt.tzinfo is None: # If naive, assume UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

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
    # timestamp: Optional[datetime] = None # REMOVED: Timestamp will not be stored per entry in DB
    question: str
    answer: List[Dict[str, Any]] # Flexible: holds AI text response or structured data

class ChatConversationDocument(BaseModel):
    reference_id: str = Field(alias="_id")
    conversation: List[ConversationEntry] = []

    class Config:
        populate_by_name = True
        # json_encoders for datetime are no longer needed here if ConversationEntry has no datetime
        # and if there are no other datetime fields at this level of the document.

# --- New Response Model for the /chat endpoint ---
class CurrentChatInteractionResponse(BaseModel):
    reference_id: str
    current_timestamp: datetime # Timestamp for THIS specific interaction
    question: str
    answer: List[Dict[str, Any]] # The answer to the current question
    # Optional: If you want to include error history for the current attempt in the response
    #error_history: Optional[List[ErrorHistoryItem]] = None

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: datetime_to_zulu
        }
