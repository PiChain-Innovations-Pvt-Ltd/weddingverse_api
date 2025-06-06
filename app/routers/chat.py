# app/routers/chat.py - Fixed with simple IST timestamps

from fastapi import APIRouter, HTTPException
from app.utils.logger import logger
from app.models.chat import ChatRequest, CurrentChatInteractionResponse, get_ist_timestamp
from app.services.chat_service import process_question

router = APIRouter()

@router.post("/chat", response_model=CurrentChatInteractionResponse)
def chat_endpoint(req: ChatRequest):
    """
    Chat endpoint with fixed IST timestamp handling.
    
    Returns properly formatted IST timestamps: "YYYY-MM-DD HH:MM:SS"
    """
    try:
        logger.info(f"Chat request for reference_id: {req.reference_id}, question: {req.question}")
        
        # Process the question
        current_question, current_answer, error_history = process_question(req.reference_id, req.question)
        
        # Get current IST timestamp for this interaction
        interaction_timestamp = get_ist_timestamp()
        
        # Construct the response with simple IST timestamp
        response = CurrentChatInteractionResponse(
            reference_id=req.reference_id,
            current_timestamp=interaction_timestamp,  # ✅ Simple IST string
            question=current_question,
            answer=current_answer,
            error_history=error_history
        )
        
        logger.info(f"Chat response ready for {req.reference_id} at {interaction_timestamp}")
        return response

    except HTTPException as he:
        # Re-raise HTTP exceptions directly
        raise he
    except Exception as e:
        logger.error(f"Error in chat_endpoint for reference_id '{req.reference_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")