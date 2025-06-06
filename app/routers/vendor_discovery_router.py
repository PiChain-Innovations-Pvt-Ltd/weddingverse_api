# app/routers/vendor_discovery_router.py - Clean Swagger without optional parameters

from fastapi import APIRouter, HTTPException, Depends, Path, Request
from typing import List, Dict, Any

from app.models.vendors import ExploreVendorsResponse
from app.services.vendor_discovery_service import get_vendors_for_category, get_supported_categories
from app.utils.logger import logger
from app.dependencies import require_jwt_auth

router = APIRouter(
    prefix="/api/v1/budget-planner/{reference_id}/category/{category_name}",
    tags=["Budget Planner - Vendor Discovery"],
    dependencies=[Depends(require_jwt_auth)]
)

# Additional router for utility endpoints
utility_router = APIRouter(
    prefix="/api/v1/vendor-discovery",
    tags=["Vendor Discovery - Utilities"],
    dependencies=[Depends(require_jwt_auth)]
)

@router.get(
    "/explore-vendors",
    response_model=ExploreVendorsResponse,
    summary="Explore Vendors for Any Category",
    description=(
        "Dynamically fetches vendors for any valid collection/category based on wedding location. "
        "Returns paginated results with vendor details including ratings, images, and contact information.\n\n"
        "**Required Parameters:**\n"
        "- `reference_id`: The unique reference ID of the budget plan\n"
        "- `category_name`: Vendor category (e.g., 'venues', 'photographers', 'catering', 'makeups', 'djs')\n\n"
        "**Default Behavior:**\n"
        "- Returns 16 vendors per page\n"
        "- Sorted by rating (highest first)\n"
        "- Starts from page 1\n\n"
        "**Supported Categories:** venues, photographers, catering, makeups, djs, decors, mehendi, bridal_wear, etc."
    )
)
async def explore_vendors_endpoint(
    reference_id: str = Path(..., description="The unique reference ID of the budget plan"),
    category_name: str = Path(..., description="Vendor category (e.g., 'venues', 'photographers', 'catering')"),
    request: Request = None
):
    """
    Explore vendors for any category - Clean endpoint with default pagination and sorting.
    
    **Usage Example:**
    ```
    GET /api/v1/budget-planner/PLAN123/category/venues/explore-vendors
    ```
    
    **Path Parameters:**
    - reference_id: Your budget plan ID
    - category_name: Vendor category to explore
    
    **Returns:**
    - List of vendors with ratings, images, and details
    - Pagination information (page, total_pages, total_vendors)
    - Default: 16 vendors per page, sorted by rating
    """
    try:
        logger.info(f"Exploring vendors: plan={reference_id}, category={category_name}")
        
        # Extract query parameters manually with defaults
        page = 1
        limit = 16
        sort_by = "Rating"
        order = "desc"
        
        # Check if request has query parameters and use them
        if request and request.query_params:
            try:
                page = int(request.query_params.get("page", 1))
                limit = int(request.query_params.get("limit", 16))
                sort_by = request.query_params.get("sort_by", "Rating")
                order = request.query_params.get("order", "desc")
                
                # Validate parameters
                if page < 1:
                    page = 1
                if limit < 1 or limit > 200:
                    limit = 16
                if order not in ["asc", "desc"]:
                    order = "desc"
                    
            except (ValueError, TypeError):
                # Use defaults if parameter parsing fails
                logger.warning(f"Invalid query parameters, using defaults")
                page, limit, sort_by, order = 1, 16, "Rating", "desc"
        
        logger.info(f"Using pagination: page={page}, limit={limit}, sort_by={sort_by}, order={order}")
        
        response_data = get_vendors_for_category(
            reference_id=reference_id,
            category_name=category_name,
            sort_by=sort_by,
            order=order,
            page=page,
            limit=limit
        )
        
        logger.info(f"Found {response_data.total_vendors} vendors in {category_name} for {reference_id}")
        return response_data
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in explore vendors endpoint for plan {reference_id}, category {category_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal server error occurred while exploring vendors.")

@utility_router.get(
    "/supported-categories",
    summary="Get All Supported Vendor Categories",
    description="Returns a list of all available vendor categories/collections that can be queried in the explore-vendors endpoint."
)
async def get_supported_categories_endpoint() -> Dict[str, Any]:
    """
    Get all supported vendor categories.
    
    **Usage Example:**
    ```
    GET /api/v1/vendor-discovery/supported-categories
    ```
    
    **Returns:**
    - List of available vendor categories
    - Total count of categories
    """
    try:
        result = get_supported_categories()
        logger.info(f"Returning {result.get('total_categories', 0)} supported categories")
        return result
    except Exception as e:
        logger.error(f"Error getting supported categories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving supported categories.")