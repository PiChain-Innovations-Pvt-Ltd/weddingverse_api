# app/routers/vendor_discovery_router.py
from fastapi import APIRouter, HTTPException, Depends, Query, Path
from typing import List, Dict, Any

from app.models.vendors import ExploreVendorsResponse
from app.services.vendor_discovery_service import get_vendors_for_category, get_supported_categories, generate_vendor_id, demonstrate_vendor_id_generation
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
    summary="Explore Vendors for Any Category with Pagination",
    description="Dynamically fetches vendors for any valid collection/category based on wedding location with pagination (10 vendors per page). Uses hash-based vendor IDs for security and stability."
)
async def explore_vendors_endpoint(
    reference_id: str = Path(..., description="The unique reference ID of the budget plan"),
    category_name: str = Path(..., description="Any valid vendor category/collection name (e.g., 'venues', 'djs', 'mehendi', 'bridal_wear', etc.)"),
    page: int = Query(1, ge=1, description="Page number for pagination (starts from 1)"),
    limit: int = Query(10, ge=1, le=100, description="Number of vendors per page (default: 10, max: 100)"),
    sort_by: str = Query("Rating", description="Field to sort by (currently only Rating is supported)"),
    order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order: 'asc' or 'desc'")
):
    try:
        response_data = get_vendors_for_category(
            reference_id=reference_id,
            category_name=category_name,
            sort_by=sort_by,
            order=order,
            page=page,
            limit=limit
        )
        return response_data
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in explore vendors endpoint for plan {reference_id}, category {category_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal server error occurred while exploring vendors.")

@utility_router.get(
    "/supported-categories",
    summary="Get All Supported Vendor Categories",
    description="Returns a list of all available vendor categories/collections that can be queried."
)
async def get_supported_categories_endpoint() -> Dict[str, Any]:
    try:
        return get_supported_categories()
    except Exception as e:
        logger.error(f"Error getting supported categories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving supported categories.")

@utility_router.get(
    "/vendor-id-demo",
    summary="Demonstrate Hash-Based Vendor ID Generation",
    description="Shows how vendor IDs are generated using deterministic hashing (not random). Educational endpoint."
)
async def vendor_id_demonstration_endpoint() -> Dict[str, Any]:
    try:
        return demonstrate_vendor_id_generation()
    except Exception as e:
        logger.error(f"Error in vendor ID demonstration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error generating vendor ID demonstration.")