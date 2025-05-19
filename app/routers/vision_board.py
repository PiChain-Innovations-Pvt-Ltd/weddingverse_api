from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from app.models.vision_board import VisionBoardRequest, VisionBoardResponse
from app.services.vision_board_service import create_vision_board
from app.utils.logger import logger

router = APIRouter()

@router.post(
    "/vision-board",
    response_model=VisionBoardResponse,
    summary="Create a wedding vision board"
)
def vision_board_endpoint(req: VisionBoardRequest):
    if not req.reference_id:
        raise HTTPException(status_code=400, detail="please provide the reference_id")
    try:
        return create_vision_board(req)
    except Exception as e:
        logger.error(f"Error in Vision‑Board endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))