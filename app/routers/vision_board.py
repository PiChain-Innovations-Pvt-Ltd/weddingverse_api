from fastapi import APIRouter, HTTPException, Path
from typing import List
from app.models.vision_board import VisionBoardRequest, VisionBoardResponse, CategoryImagesResponse, EventImagesResponse  # MODIFIED: Added CategoryImagesResponse
from app.utils.logger import logger
from app.services.vision_board_service import (
    create_vision_board, 
    get_vision_boards_by_id, 
    get_vision_board_images_by_category,
    get_vision_board_images_by_event  
)
import json
from app.services.mongo_service import db
from app.config import settings, FIELD_MAP
from app.services.genai_service import model


IMAGE_INPUT_COLLECTION = settings.image_input_collection
VISION_BOARD_COLLECTION = settings.VISION_BOARD_COLLECTION
router = APIRouter()

CATEGORY_MAPPING = {
    # Frontend category -> Database keywords
    "venues": [
        "venues", "venue"
    ],
    "fashion and attire": [
        "wedding_wear", "bridalWear"
    ],
    "decor": [
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
async def get_vision_board_images_by_event_endpoint(
    reference_id: str = Path(..., description="The unique reference ID of the vision board(s)"),
    event: str = Path(..., description="Event to filter images by")
):
    """
    Retrieve all unique image links from vision boards that contain the specified event in their events field.
    
    The events are dynamically validated based on the actual events present in the vision boards 
    for the given reference_id.
    
    Note: Event matching is case-insensitive.
    """
    
    try:
        # SIMPLIFIED: Get available events directly in the endpoint
        cursor = db[VISION_BOARD_COLLECTION].find(
            {"reference_id": reference_id},
            {"_id": 0, "events": 1}
        )
        
        board_docs = list(cursor)
        
        if not board_docs:
            raise HTTPException(
                status_code=404,
                detail=f"No vision boards found for reference_id: {reference_id}"
            )
        
        # Collect all unique events
        all_events = set()
        for doc in board_docs:
            events = doc.get("events", [])
            if isinstance(events, list):
                for evt in events:
                    if isinstance(evt, str) and evt.strip():
                        all_events.add(evt.strip())
        
        available_events = list(all_events)
        
        # Dynamic validation against actual events
        event_found = False
        matched_event = None
        
        for available_event in available_events:
            if event.lower() == available_event.lower():
                event_found = True
                matched_event = available_event
                break
        
        if not event_found:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid event '{event}'. Available events for this reference_id are: {', '.join(sorted(available_events))}"
            )
        
        # Call service function with the matched event
        result = await get_vision_board_images_by_event(reference_id, matched_event)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving {event} images for {reference_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")