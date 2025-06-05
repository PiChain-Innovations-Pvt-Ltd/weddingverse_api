# app/routers/vendor_details_router.py
from fastapi import APIRouter, HTTPException, Depends, Path

from app.models.vendors import VendorDetailsResponse
from app.services.vendor_details_service import get_vendor_details_by_id
from app.utils.logger import logger
from app.dependencies import require_jwt_auth

router = APIRouter(
    prefix="/api/v1/vendor-details",
    tags=["Vendor Details"],
    dependencies=[Depends(require_jwt_auth)]
)

@router.get(
    "/category/{category_name}/vendor/{vendor_id}",
    response_model=VendorDetailsResponse,
    summary="Get Complete Vendor Information",
    description="Fetches complete vendor information by vendor_id for messaging or detailed view. Returns all available fields from the vendor document."
)
async def get_vendor_details_endpoint(
    category_name: str = Path(..., description="The vendor category/collection name (e.g., 'venues', 'photographers', etc.)"),
    vendor_id: str = Path(..., description="The MongoDB ObjectId of the vendor")
):
    """
    Get complete vendor details by vendor ID and category.
    
    This endpoint is used when:
    - User clicks "Send Message" on a vendor card
    - User wants to view detailed vendor information
    - Frontend needs complete vendor data for forms or modals
    
    Args:
        category_name: The collection name where the vendor exists
        vendor_id: The MongoDB ObjectId of the vendor
        
    Returns:
        Complete vendor information including all available fields
    """
    try:
        logger.info(f"Fetching vendor details for vendor_id: {vendor_id} from category: {category_name}")
        vendor_details = get_vendor_details_by_id(vendor_id, category_name)
        return VendorDetailsResponse(vendor=vendor_details)
        
    except HTTPException as he:
        logger.warning(f"HTTP error fetching vendor {vendor_id} in {category_name}: {he.detail}")
        raise he
    except Exception as e:
        logger.error(f"Unexpected error fetching vendor details for {vendor_id} in category {category_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal server error occurred while fetching vendor details.")