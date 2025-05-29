# app/routers/webhook.py
from fastapi import APIRouter, status, HTTPException
from app.models.webhook import WebhookPayload
from app.services import webhook_workflow_service # New service
from app.utils.logger import logger

router = APIRouter()

@router.post(
    "/webhook",
    response_model=dict,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger General Workflow from Webhook",
)

async def receive_general_webhook(payload: WebhookPayload):
    """
    Receives an incoming webhook payload and initiates a general workflow process.
    The processing happens asynchronously in the background.
    """
    logger.info(f"⚡️ General Webhook received for Call ID: {payload.call_id}")
    try:
        if payload.client == "WeddingVerse":
            logger.info(f"⚡️ Webhook received: {payload}")
            # Delegate the entire workflow orchestration to the new service layer
            workflow_results = await webhook_workflow_service.process_webhook_workflow(payload)
            
            return {
                "status": "processing_initiated",
                "message": "Webhook received and workflow processing started asynchronously.",
                "details": workflow_results
            }
        logger.info("The client is not from WeddingVerse")
    except Exception as e:
        logger.error(f"Failed to process general webhook for call_id {payload.call_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate workflow: {str(e)}"
        )