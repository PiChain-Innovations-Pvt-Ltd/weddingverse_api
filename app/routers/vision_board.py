from fastapi import APIRouter, HTTPException, Path
from typing import List
from app.models.vision_board import VisionBoardRequest, VisionBoardResponse
from app.services.vision_board_service import create_vision_board, get_vision_boards_by_id
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
    

@router.get(
    "/vision-board/{reference_id}",
    response_model=List[VisionBoardResponse],
    summary="Retrieve all wedding vision boards by reference ID"
)
async def get_vision_board(
    reference_id: str = Path(..., description="The unique reference ID of the vision board(s)")
):
    try:
        vision_board_data = await get_vision_boards_by_id(reference_id) # MODIFIED: Call new service function
        return vision_board_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving vision boards for {reference_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")