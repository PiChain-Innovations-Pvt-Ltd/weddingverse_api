# weddingverse_api/app/models/webhook.py
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

class TranscriptMessageTimespan(BaseModel):
    start: str
    end: str

class TranscriptMessage(BaseModel):
    role: str
    text: Optional[str] = None 
    medium: str
    callStageId: str
    callStageMessageIndex: int
    invocationId: Optional[str] = None
    toolName: Optional[str] = None
    timespan: Optional[TranscriptMessageTimespan] = None # Use the nested Pydantic model

class WebhookPayload(BaseModel):
    """
    Represents the incoming data from the webhook for vendor onboarding.
    Adjusted to closely match the provided JSON structure.
    """
    call_id: str = Field(..., alias="callId") # Map callId from input to call_id in model
    transcript: List[TranscriptMessage]
    client: Optional[str] = None