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
    try:
        return create_vision_board(req)
    except HTTPException as he:
        # Re-raise HTTP exceptions to maintain the correct status code
        raise he
    except Exception as e:
        logger.error(f"Error in /vision-board: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))