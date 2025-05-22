from fastapi import APIRouter, HTTPException
from app.utils.logger import logger
from app.models.chat import ChatRequest, ChatConversationDocument
from app.services.chat_service import process_question

router = APIRouter()

@router.post("/chat") # No `response_model` here, we return a dict
def chat_endpoint(req: ChatRequest):
    try:
        conversation_document: ChatConversationDocument = process_question(req.reference_id, req.question)
        
        # Serialize the Pydantic model to a dictionary,
        # excluding any fields that are None (like historical timestamps).
        # by_alias=True ensures "_id" is used if specified in the model.
        return conversation_document.model_dump(by_alias=True, exclude_none=True)

    except HTTPException as he: # Re-raise HTTPExceptions directly
        raise he
    except Exception as e:
        logger.error(f"Error in chat_endpoint for reference_id '{req.reference_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")