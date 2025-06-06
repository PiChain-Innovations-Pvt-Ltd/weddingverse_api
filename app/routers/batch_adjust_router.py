# app/routers/batch_adjust_router.py - Fixed with IST timestamp

from fastapi import APIRouter, HTTPException, Depends, Path, Body
from dateutil import tz
from datetime import datetime
from app.models.budget import (
    BatchAdjustEstimatesFixedTotalRequest,
    BudgetPlannerAPIResponse,
    BudgetPlanDBSchema
)
from app.services.batch_adjust_service import process_batch_adjustments_fixed_total
from app.utils.logger import logger
from app.dependencies import require_jwt_auth

router = APIRouter(
    prefix="/api/v1/budget-planner/{reference_id}",
    tags=["Budget Planner - Batch Adjustments (Fixed Total)"],
    dependencies=[Depends(require_jwt_auth)]
)

# Simple IST timestamp utility
def get_ist_timestamp() -> str:
    """Get current timestamp in IST format: YYYY-MM-DD HH:MM:SS"""
    ist = tz.gettz("Asia/Kolkata")
    return datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

@router.post(
    "/batch-adjust-fixed-total",
    response_model=BudgetPlannerAPIResponse,
    summary="Batch Adjust, Add, Delete Categories & Edit Total Budget",
    description=(
        "Comprehensive budget management endpoint that can: "
        "1. UPDATE existing category estimates, actual costs, and payment statuses. "
        "2. ADD new expense categories with initial estimates, actual costs, and payment statuses. "
        "3. DELETE existing categories (estimates redistributed to remaining categories). "
        "4. CHANGE the total budget amount. "
        "The new_total_budget field logic: "
        "- If new_total_budget > 0: Updates budget to this new amount. "
        "- If new_total_budget = 0: Keeps existing budget unchanged. "
        "When categories are deleted, their estimates are redistributed proportionally among remaining categories. "
        "If all categories are deleted, the full budget amount goes to balance. "
        "New categories are added at the end of the budget breakdown."
    )
)
async def endpoint_batch_adjust_estimates_fixed_total(
    reference_id: str = Path(..., description="The unique reference ID of the budget plan"),
    request_body: BatchAdjustEstimatesFixedTotalRequest = Body(
        ...,
        examples={
            "update_existing_keep_budget": {
                "summary": "Update existing categories (keep current budget)",
                "description": "Set new_total_budget to 0 to maintain existing budget while adjusting categories",
                "value": {
                    "new_total_budget": 0,
                    "adjustments": [
                        {"category_name": "Venue", "new_estimate": 15000, "actual_cost": 10000, "payment_status": "Partially Paid"},
                        {"category_name": "Photography", "new_estimate": 8000, "actual_cost": 8000, "payment_status": "Paid"}
                    ],
                    "deletions": []
                }
            },
            "add_new_categories_keep_budget": {
                "summary": "Add new categories (keep current budget)",
                "description": "Set new_total_budget to 0 to maintain existing budget while adding new categories",
                "value": {
                    "new_total_budget": 0,
                    "adjustments": [
                        {"category_name": "Videographer", "new_estimate": 12000, "actual_cost": 0, "payment_status": "Not Paid"},
                        {"category_name": "Favors", "new_estimate": 8000, "actual_cost": 8000, "payment_status": "Paid"}
                    ],
                    "deletions": []
                }
            },
            "delete_categories": {
                "summary": "Delete categories and redistribute amounts",
                "description": "Delete specified categories and redistribute their estimates proportionally among remaining categories",
                "value": {
                    "new_total_budget": 0,
                    "adjustments": [],
                    "deletions": [
                        {"category_name": "DJ"},
                        {"category_name": "Mehendi"}
                    ]
                }
            },
            "mixed_operations_keep_budget": {
                "summary": "Delete, update, and add categories (keep current budget)",
                "description": "Combine deletions, updates (with actual_cost/status), and new additions while keeping existing budget",
                "value": {
                    "new_total_budget": 0,
                    "adjustments": [
                        {"category_name": "Venue", "new_estimate": 15000, "actual_cost": 14000, "payment_status": "Paid"},
                        {"category_name": "Decorator", "new_estimate": 5000, "actual_cost": 2000, "payment_status": "Partially Paid"}
                    ],
                    "deletions": [
                        {"category_name": "DJ"},
                        {"category_name": "Mehendi"}
                    ]
                }
            }
        }
    )
):
    try:
        # Check if there are any operations to perform
        has_adjustments = bool(request_body.adjustments)
        has_deletions = bool(request_body.deletions)
        has_budget_change = request_body.new_total_budget > 0
        
        if not has_adjustments and not has_deletions and not has_budget_change:
            raise HTTPException(
                status_code=400, 
                detail="No operations specified. Please provide adjustments, deletions, or a new budget amount."
            )

        logger.info(f"Processing batch adjustments for reference_id: {reference_id}")
        
        # Process the batch adjustments
        processed_plan: BudgetPlanDBSchema = process_batch_adjustments_fixed_total(
            reference_id,
            request_body
        )

        # ✅ Get current IST timestamp for the API response
        current_timestamp = get_ist_timestamp()
        
        # ✅ Create API response with proper timestamp
        api_response = BudgetPlannerAPIResponse(
            reference_id=processed_plan.reference_id,
            timestamp=current_timestamp,  # Use current IST timestamp
            total_budget=processed_plan.current_total_budget,
            budget_breakdown=processed_plan.budget_breakdown,
            spent=processed_plan.total_spent,
            balance=processed_plan.balance,
            selected_vendors=processed_plan.selected_vendors
        )
        
        logger.info(f"Batch adjustments completed for {reference_id} at {current_timestamp}")
        return api_response
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Unexpected error during batch estimate adjustment for plan {reference_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during batch estimate adjustment.")