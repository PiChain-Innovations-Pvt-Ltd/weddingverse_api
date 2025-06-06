# app/routers/vendor_selection_router.py - Fixed with IST timestamp

from fastapi import APIRouter, HTTPException, Depends, Path
from dateutil import tz
from datetime import datetime
from app.models.budget import BudgetPlannerAPIResponse, BudgetPlanDBSchema
from app.services.vendor_selection_service import add_selected_vendor_to_plan
from app.utils.logger import logger
from app.dependencies import require_jwt_auth

router = APIRouter(
    prefix="/api/v1/budget-planner/{reference_id}/category/{category_name}",
    tags=["Budget Planner - Vendor Selection"],
    dependencies=[Depends(require_jwt_auth)]
)

# Simple IST timestamp utility
def get_ist_timestamp() -> str:
    """Get current timestamp in IST format: YYYY-MM-DD HH:MM:SS"""
    ist = tz.gettz("Asia/Kolkata")
    return datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

@router.post(
    "/select-vendor/{vendor_id}",
    response_model=BudgetPlannerAPIResponse,
    summary="Add a Selected Vendor to the Budget Plan",
    description=(
        "Adds a specified vendor to the 'selected_vendors' list within the user's budget plan for a given category. "
        "The vendor details are automatically fetched from the database using the vendor_id and category_name. "
        "If the exact vendor (same `vendor_id` within the `category_name`) already exists, its details will be updated. "
        "This allows users to keep track of vendors they are interested in or have booked."
    )
)
async def select_vendor_endpoint(
    reference_id: str = Path(..., description="The unique reference ID of the budget plan"),
    category_name: str = Path(..., description="The category of the vendor being selected (e.g., 'venues', 'photographers')"),
    vendor_id: str = Path(..., description="The MongoDB ObjectId of the vendor to be selected")
):
    """
    Select a vendor and add to budget plan with IST timestamp.
    
    This endpoint:
    1. Fetches vendor details from the appropriate collection
    2. Adds vendor to the selected_vendors list in budget plan
    3. Returns updated budget plan with IST timestamp
    
    Args:
        reference_id: Budget plan reference ID
        category_name: Vendor category (venues, photographers, etc.)
        vendor_id: MongoDB ObjectId of the vendor
        
    Returns:
        Updated budget plan with selected vendor and IST timestamp
    """
    try:
        logger.info(f"Selecting vendor {vendor_id} in category {category_name} for plan {reference_id}")
        
        # Add the selected vendor to the plan
        updated_plan: BudgetPlanDBSchema = add_selected_vendor_to_plan(reference_id, category_name, vendor_id)
        
        # ✅ Get current IST timestamp for the API response
        current_timestamp = get_ist_timestamp()
        
        # ✅ Construct the API response with proper timestamp
        api_response = BudgetPlannerAPIResponse(
            reference_id=updated_plan.reference_id,
            timestamp=current_timestamp,  # Use current IST timestamp
            total_budget=updated_plan.current_total_budget,
            budget_breakdown=updated_plan.budget_breakdown,
            spent=updated_plan.total_spent,
            balance=updated_plan.balance,
            selected_vendors=updated_plan.selected_vendors
        )
        
        logger.info(f"Vendor selection completed for {reference_id} at {current_timestamp}")
        return api_response
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Unexpected error during vendor selection for plan {reference_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during vendor selection.")