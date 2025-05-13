# app/routers/vision_board.py

from fastapi import APIRouter, HTTPException
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
    try:
        return create_vision_board(req)
    except Exception as e:
        logger.error("Error in /vision-board", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
