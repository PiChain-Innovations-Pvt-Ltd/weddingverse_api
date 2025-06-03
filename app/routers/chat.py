# from fastapi import APIRouter, HTTPException
# from app.utils.logger import logger
# from app.models.chat import ChatRequest, ChatResponse
# from app.services.chat_service import process_question

# router = APIRouter()

# @router.post("/chat", response_model=ChatResponse)
# def chat_endpoint(req: ChatRequest):
#     try:
#         return process_question(req.question)
#     except Exception as e:
#         logger.error(f"Error in endpoint {router}: {e}", exc_info=True)
#         raise HTTPException(status_code=500, detail=str(e))


from fastapi import APIRouter, HTTPException
from app.utils.logger import logger
from app.models.chat import ChatRequest, CurrentChatInteractionResponse # Changed model
from app.services.chat_service import process_question
from datetime import datetime, timezone # Added for timestamp

router = APIRouter()

@router.post("/chat", response_model=CurrentChatInteractionResponse) # Updated response_model
def chat_endpoint(req: ChatRequest):
    try:
        # process_question now returns current Q, A, and error history
        current_question, current_answer, error_history = process_question(req.reference_id, req.question)
        
        # Get current timestamp for this interaction
        interaction_timestamp = datetime.now(timezone.utc)

        # Construct the response using the new model
        response = CurrentChatInteractionResponse(
            reference_id=req.reference_id,
            current_timestamp=interaction_timestamp,
            question=current_question,
            answer=current_answer,
            error_history=error_history # Pass along error history if any
        )
        
        return response

    except HTTPException as he: # Re-raise HTTPExceptions directly
        raise he
    except Exception as e:
        logger.error(f"Error in chat_endpoint for reference_id '{req.reference_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")
