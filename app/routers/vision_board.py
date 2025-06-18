from fastapi import APIRouter, HTTPException, Path
from typing import List
from app.models.vision_board import VisionBoardRequest, VisionBoardResponse, CategoryImagesResponse  # MODIFIED: Added CategoryImagesResponse
from app.services.vision_board_service import create_vision_board, get_vision_boards_by_id, get_vision_board_images_by_category  # MODIFIED: Added new service function
from app.utils.logger import logger

router = APIRouter()

CATEGORY_MAPPING = {
    # Frontend category -> Database keywords
    "venue": [
        "venue"
    ],
    "decor": [
        "decor"
    ],
    "attire": [
        
        "brideWear"
    ]
}
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

# NEW ENDPOINT ADDED
# @router.get(
#     "/vision-board/{reference_id}/category/{category}",
#     response_model=CategoryImagesResponse,
#     summary="Get vision board images filtered by category (venue, decor, attire)"
# )
# async def get_vision_board_images_by_category_endpoint(
#     reference_id: str = Path(..., description="The unique reference ID of the vision board(s)"),
#     category: str = Path(..., description="Category to filter images by (venue, decor, attire)")
# ):
#     """
#     Retrieve all image links from vision boards that contain the specified category in their URL.
    
#     Supported categories:
#     - venue: Returns images with 'venue' in the URL
#     - decor: Returns images with 'decor' in the URL  
#     - attire: Returns images with 'attire' or 'fashion' in the URL
#     """
    
#     # Validate category
#     valid_categories = ["venue", "decor", "attire"]
#     if category.lower() not in valid_categories:
#         raise HTTPException(
#             status_code=400, 
#             detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}"
#         )
    
#     try:
#         result = await get_vision_board_images_by_category(reference_id, category.lower())
#         return result
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error retrieving {category} images for {reference_id}: {e}", exc_info=True)
#         raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}") 


@router.get(
    "/vision-board/{reference_id}/category/{category}",
    response_model=CategoryImagesResponse,
    summary="Get vision board images filtered by category (venue, decor, attire)"
)
async def get_vision_board_images_by_category_endpoint(
    reference_id: str = Path(..., description="The unique reference ID of the vision board(s)"),
    category: str = Path(..., description="Category to filter images by (venue, decor, attire)")
):
    """
    Retrieve all image links from vision boards that contain the specified category in their URL.
    
    Supported categories:
    - venue: Returns images with venue-related keywords
    - decor: Returns images with decoration-related keywords  
    - attire: Returns images with clothing/fashion keywords (including brideWear, groomWear variations)
    
    Note: The system handles various naming conventions including brideWear, bride_wear, etc.
    """
    
    # Validate category
    valid_categories = list(CATEGORY_MAPPING.keys())
    if category.lower() not in valid_categories:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}"
        )
    
    try:
        result = await get_vision_board_images_by_category(reference_id, category.lower())
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving {category} images for {reference_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")