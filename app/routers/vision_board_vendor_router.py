# app/routers/vision_board_vendor_router.py

from fastapi import APIRouter, HTTPException, Depends, Path, Query, status
from typing import Optional
from app.models.vendors import ExploreVendorsResponse
from app.services.vision_board_vendor_service import get_vision_board_vendors
from app.dependencies import get_bearer_token # New dependency to get the raw token
from app.utils.logger import logger

router = APIRouter(
    prefix="/api/v1/vision-board-vendors",
    tags=["Vision Board - Vendor Discovery"]
)

@router.get(
    "/{reference_id}/category/{category_name}",
    response_model=ExploreVendorsResponse,
    summary="Get Vendors from Vision Board by Category",
    description=(
        "Fetches a list of vendors associated with a user's vision board for a specific category. "
        "It first queries an external vision board API to get relevant vendor IDs and image links, "
        "then retrieves detailed vendor information from the database. "
        "Supports pagination and sorting by rating."
    )
)
async def get_vendors_from_vision_board_endpoint(
    reference_id: str = Path(..., description="The unique reference ID of the vision board"),
    category_name: str = Path(..., description="The category name (e.g., 'fashion and attire', 'decor', 'venues')"),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    limit: int = Query(16, ge=1, le=200, description="Number of vendors per page (max 200)"),
    sort_by: str = Query("Rating", description="Field to sort by (e.g., 'Rating', 'Title')"),
    order: str = Query("desc", description="Sort order ('asc' for ascending, 'desc' for descending)"),
    auth_token: str = Depends(get_bearer_token) # Inject the raw bearer token
):
    """
    Retrieve vendors linked to a vision board, filtered by category.
    
    This endpoint performs the following steps:
    1. Calls an external API to get image links and vendor IDs associated with the vision board and category.
    2. Uses the extracted vendor IDs to fetch detailed vendor information from the internal database.
    3. Applies pagination and sorts the results based on the specified criteria.
    
    Args:
        reference_id: The unique reference ID of the vision board.
        category_name: The category of vendors to retrieve (e.g., 'fashion and attire', 'decor', 'venues').
        page: The page number for pagination (default: 1).
        limit: The maximum number of vendors to return per page (default: 16, max: 200).
        sort_by: The field to sort the vendors by (default: 'Rating').
        order: The sort order ('asc' for ascending, 'desc' for descending, default: 'desc').
        auth_token: The JWT bearer token for authentication with the external API.
        
    Returns:
        ExploreVendorsResponse: A paginated list of vendor items with their details.
    """
    try:
        logger.info(f"Request to get vision board vendors: ref_id={reference_id}, category={category_name}, page={page}, limit={limit}, sort_by={sort_by}, order={order}")
        
        response = await get_vision_board_vendors(
            reference_id=reference_id,
            category_name=category_name,
            auth_token=auth_token,
            page=page,
            limit=limit,
            sort_by=sort_by,
            order=order
        )
        return response
    except HTTPException as he:
        logger.warning(f"HTTP Exception in vision board vendor endpoint: {he.detail}")
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in vision board vendor endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal server error occurred.")