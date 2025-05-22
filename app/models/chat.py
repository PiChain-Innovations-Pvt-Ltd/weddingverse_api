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
# The primary response for the /chat endpoint is now ChatConversationDocument.
class ChatResponse(BaseModel):
    reference_id: str
    timestamp: str
    question: str
    response_type: str # e.g., 'mongo_query', 'conversation'
    response: Optional[str] = None # For direct LLM text
    mongo_query: Optional[str] = None
    results: Optional[List[MongoResult]] = None # For structured query results
    error: Optional[str] = None
    error_history: Optional[List[ErrorHistoryItem]] = None
    table_output: Optional[str] = None


# --- Models for Chat Conversation Collection ---

class ConversationEntry(BaseModel):
    timestamp: Optional[datetime] = None # For new entries, we'll set this; for historical, it will be None due to projection
    question: str
    answer: List[Dict[str, Any]] # Flexible: holds AI text response or structured data
    # answer_source was removed

class ChatConversationDocument(BaseModel):
    reference_id: str = Field(alias="_id")
    # start_time and last_updated were removed
    conversation: List[ConversationEntry] = []

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: datetime_to_zulu # This will apply to ConversationEntry.timestamp when it's present
        }