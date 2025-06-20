# app/routers/vendor_details_router.py
from fastapi import APIRouter, HTTPException, Depends, Path, status
from app.models.vendors import VendorDetailsResponse
from app.services.vendor_details_service import get_vendor_details_by_name 
from app.utils.logger import logger
from app.dependencies import require_jwt_auth

router = APIRouter(
    prefix="/api/v1/vendor-details",
    tags=["Vendor Details"],
    dependencies=[Depends(require_jwt_auth)]
)

@router.get(
    "/{reference_id}/category/{category_name}/vendor/{vendor_name}",
    response_model=VendorDetailsResponse,
    summary="Get Complete Vendor Information by Name",
    description="Fetches complete vendor information by vendor name for messaging or detailed view. Returns all available fields from the vendor document."
)
async def get_vendor_details_endpoint(
    reference_id: str = Path(..., description="The unique reference ID associated with the user or context"),
    category_name: str = Path(..., description="The vendor category/collection name (e.g., 'venues', 'photographers', etc.)"),
    vendor_name: str = Path(..., description="The name of the vendor (e.g., 'House of Tushaom', 'SKN Kalyana Mantapa')")
):
    """
    Get complete vendor details by vendor name and category.
    
    This endpoint is used when:
    - User clicks "Send Message" on a vendor card
    - User wants to view detailed vendor information
    - Frontend needs complete vendor data for forms or modals
    
    Args:
        reference_id: The unique reference ID for the user or context.
        category_name: The collection name where the vendor exists
        vendor_name: The name of the vendor
        
    Returns:
        Complete vendor information including all available fields
    """
    try:
        logger.info(f"Fetching vendor details for ref_id: '{reference_id}', vendor_name: '{vendor_name}' from category: '{category_name}'")
        vendor_details = get_vendor_details_by_name(reference_id, vendor_name, category_name)
        # NEW: Pass reference_id to the response model
        return VendorDetailsResponse(reference_id=reference_id, vendor=vendor_details)
        
    except HTTPException as he:
        logger.warning(f"HTTP error fetching vendor '{vendor_name}' in '{category_name}': {he.detail}")
        raise he
    except Exception as e:
        logger.error(f"Unexpected error fetching vendor details for '{vendor_name}' in category '{category_name}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal server error occurred while fetching vendor details.")