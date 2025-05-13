from pydantic import BaseModel
from typing import Any, List, Optional

class ChatRequest(BaseModel):
    question: str

class ErrorHistoryItem(BaseModel):
    attempt: int
    query: Optional[str]
    error: str
    fix: Optional[str] = None

class MongoResult(BaseModel):
    collection: str
    filter: Any
    projection: Any
    results: List[Any]

class ChatResponse(BaseModel):
    reference_id: str
    timestamp: str
    question: str
    response_type: str
    response: Optional[str] = None
    mongo_query: Optional[str] = None
    results: Optional[List[MongoResult]] = None
    error: Optional[str] = None
    error_history: Optional[List[ErrorHistoryItem]] = None
    table_output: Optional[str] = None
