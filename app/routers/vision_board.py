# from fastapi import APIRouter, HTTPException, Path
# from typing import List
# from app.models.vision_board import VisionBoardRequest, VisionBoardResponse, CategoryImagesResponse, EventImagesResponse  # MODIFIED: Added CategoryImagesResponse
# from app.services.vision_board_service import create_vision_board, get_vision_boards_by_id, get_vision_board_images_by_category  # MODIFIED: Added new service function
# from app.utils.logger import logger

# router = APIRouter()

# CATEGORY_MAPPING = {
#     # Frontend category -> Database keywords
#     "venues": [
#         "venues", "venue"
#     ],
#     "fashion and attire": [
#         "wedding_wear", "bridalWear"
#     ],
#     "decors": [
#         "decors", "decor"
#     ]
# }
# @router.post(
#     "/vision-board",
#     response_model=VisionBoardResponse,
#     summary="Create a wedding vision board"
# )
# def vision_board_endpoint(req: VisionBoardRequest):
#     if not req.reference_id:
#         raise HTTPException(status_code=400, detail="please provide the reference_id")
#     try:
#         return create_vision_board(req)
#     except Exception as e:
#         logger.error(f"Error in Vision‑Board endpoint: {e}", exc_info=True)
#         raise HTTPException(status_code=500, detail=str(e))
       

# @router.get(
#     "/vision-board/{reference_id}",
#     response_model=List[VisionBoardResponse],
#     summary="Retrieve all wedding vision boards by reference ID"
# )
# async def get_vision_board(
#     reference_id: str = Path(..., description="The unique reference ID of the vision board(s)")
# ):
#     try:
#         vision_board_data = await get_vision_boards_by_id(reference_id) # MODIFIED: Call new service function
#         return vision_board_data
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error retrieving vision boards for {reference_id}: {e}", exc_info=True)
#         raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

# # NEW ENDPOINT ADDED
# # @router.get(
# #     "/vision-board/{reference_id}/category/{category}",
# #     response_model=CategoryImagesResponse,
# #     summary="Get vision board images filtered by category (venue, decor, attire)"
# # )
# # async def get_vision_board_images_by_category_endpoint(
# #     reference_id: str = Path(..., description="The unique reference ID of the vision board(s)"),
# #     category: str = Path(..., description="Category to filter images by (venue, decor, attire)")
# # ):
# #     """
# #     Retrieve all image links from vision boards that contain the specified category in their URL.
    
# #     Supported categories:
# #     - venue: Returns images with 'venue' in the URL
# #     - decor: Returns images with 'decor' in the URL  
# #     - attire: Returns images with 'attire' or 'fashion' in the URL
# #     """
    
# #     # Validate category
# #     valid_categories = ["venue", "decor", "attire"]
# #     if category.lower() not in valid_categories:
# #         raise HTTPException(
# #             status_code=400, 
# #             detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}"
# #         )
    
# #     try:
# #         result = await get_vision_board_images_by_category(reference_id, category.lower())
# #         return result
# #     except HTTPException:
# #         raise
# #     except Exception as e:
# #         logger.error(f"Error retrieving {category} images for {reference_id}: {e}", exc_info=True)
# #         raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}") 


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
#     - venue: Returns images with venue-related keywords
#     - decor: Returns images with decoration-related keywords  
#     - attire: Returns images with clothing/fashion keywords (including brideWear, groomWear variations)
    
#     Note: The system handles various naming conventions including brideWear, bride_wear, etc.
#     """
    
#     # Validate category
#     valid_categories = list(CATEGORY_MAPPING.keys())
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
    
    
# @router.get(
#     "/vision-board/{reference_id}/event/{event}",
#     response_model=EventImagesResponse,
#     summary="Get vision board images filtered by event (Haldi, Mehendi, Wedding Celebration)"
# )
# async def get_vision_board_images_by_event(
#     reference_id: str = Path(..., description="The unique reference ID of the vision board(s)"),
#     event: str = Path(..., description="Event to filter images by (Haldi, Mehendi, Wedding Celebration)")
# ):
#     """
#     Retrieve all unique image links from vision boards that contain the specified event in their events field.
    
#     Supported events:
#     - Haldi: Returns images associated with Haldi ceremony
#     - Mehendi: Returns images associated with Mehendi ceremony  
#     - Wedding Celebration: Returns images associated with Wedding Celebration
    
#     Note: The system extracts images from vendor_mappings field and removes duplicates.
#     """
    
#     # Validate event (you can customize these based on your actual event names)
#     valid_events = ["Haldi", "mehendi", "wedding celebration","Pre-Wedding"]
#     if event.lower() not in valid_events:
#         raise HTTPException(
#             status_code=400, 
#             detail=f"Invalid event. Must be one of: {', '.join(valid_events)}"
#         )
    
#     try:
#         result = await get_vision_board_images_by_event(reference_id, event.lower())
#         return result
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error retrieving {event} images for {reference_id}: {e}", exc_info=True)
#         raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


from fastapi import APIRouter, HTTPException, Path
from typing import List
from app.models.vision_board import VisionBoardRequest, VisionBoardResponse, CategoryImagesResponse, EventImagesResponse  # MODIFIED: Added CategoryImagesResponse
#from app.services.vision_board_service import create_vision_board, get_vision_boards_by_id, get_vision_board_images_by_category  # MODIFIED: Added new service function
from app.utils.logger import logger
from app.services.vision_board_service import (
    create_vision_board, 
    get_vision_boards_by_id, 
    get_vision_board_images_by_category,
    get_vision_board_images_by_event  
)
router = APIRouter()

CATEGORY_MAPPING = {
    # Frontend category -> Database keywords
    "venues": [
        "venues", "venue"
    ],
    "fashion and attire": [
        "wedding_wear", "bridalWear"
    ],
    "decors": [
        "decors", "decor"
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
    
    
@router.get(
    "/vision-board/{reference_id}/event/{event}",
    response_model=EventImagesResponse,
    summary="Get vision board images filtered by event"
)
async def get_vision_board_images_by_event_endpoint(  # RENAMED to avoid conflict
    reference_id: str = Path(..., description="The unique reference ID of the vision board(s)"),
    event: str = Path(..., description="Event to filter images by")
):
    """
    Retrieve all unique image links from vision boards that contain the specified event in their events field.
    
    Supported events:
    - Haldi: Returns images associated with Haldi ceremony
    - mehendi: Returns images associated with Mehendi ceremony  
    - wedding celebration: Returns images associated with Wedding Celebration
    - Pre-Wedding: Returns images associated with Pre-Wedding events
    
    Note: Event matching is case-insensitive.
    """
    
    # Valid events (case-insensitive)
    valid_events = ["haldi", "mehendi", "wedding celebration", "pre-wedding"]
    
    # FIXED: Use case-insensitive comparison
    if event.lower() not in valid_events:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid event. Must be one of: {', '.join(['Haldi', 'mehendi', 'wedding celebration', 'Pre-Wedding'])}"
        )
    
    try:
        # Call service function with original case
        result = await get_vision_board_images_by_event(reference_id, event)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving {event} images for {reference_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
