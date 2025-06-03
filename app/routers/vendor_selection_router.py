# weddingverse_api15/app/routers/vendor_selection_router.py
from fastapi import APIRouter, HTTPException, Depends, Path
from app.models.budget import BudgetPlannerAPIResponse, BudgetPlanDBSchema
from app.services.vendor_selection_service import add_selected_vendor_to_plan
from app.utils.logger import logger
from app.dependencies import require_jwt_auth

router = APIRouter(
    prefix="/api/v1/budget-planner/{reference_id}/category/{category_name}",
    tags=["Budget Planner - Vendor Selection"],
    dependencies=[Depends(require_jwt_auth)]
)

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
    try:
        # Pass all three parameters to the service function
        updated_plan: BudgetPlanDBSchema = add_selected_vendor_to_plan(reference_id, category_name, vendor_id)
        
        # Construct the API response
        api_response = BudgetPlannerAPIResponse(
            reference_id=updated_plan.reference_id,
            timestamp=updated_plan.timestamp,
            total_budget=updated_plan.current_total_budget,
            budget_breakdown=updated_plan.budget_breakdown,
            spent=updated_plan.total_spent,
            balance=updated_plan.balance,
            selected_vendors=updated_plan.selected_vendors
        )
        return api_response
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Unexpected error during vendor selection for plan {reference_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during vendor selection.")