from fastapi import APIRouter, HTTPException
from app.utils.logger import logger
from app.models.chat import ChatRequest, ChatResponse
from app.services.chat_service import process_question

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    try:
        return process_question(req.question)
    except Exception as e:
        logger.error(f"Error in endpoint {router}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
