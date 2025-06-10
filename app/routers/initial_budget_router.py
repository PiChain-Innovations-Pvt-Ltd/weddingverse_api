# app/routers/initial_budget_router.py - Fixed with IST timestamp

from fastapi import APIRouter, HTTPException, Depends
from dateutil import tz
from datetime import datetime
from app.models.budget import InitialBudgetSetupRequest, BudgetPlannerAPIResponse, BudgetPlanDBSchema
from app.services.budget_service import create_initial_budget_plan
from app.utils.logger import logger
from app.dependencies import require_jwt_auth

router = APIRouter(
    prefix="/api/v1",
    tags=["Budget Planner - Initial Setup"],
    dependencies=[Depends(require_jwt_auth)]
)

# Simple IST timestamp utility
def get_ist_timestamp() -> str:
    """Get current timestamp in IST format: YYYY-MM-DD HH:MM:SS"""
    ist = tz.gettz("Asia/Kolkata")
    return datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

@router.post(
    "/budget-planner",
    response_model=BudgetPlannerAPIResponse,
    summary="Create Initial Budget Plan",
    description=(
        "Create a new wedding budget plan with automatic category distribution. "
        "The budget is automatically divided into predefined categories: "
        "Venue (25%), Caterer (25%), Photography (25%), Makeup (25%). "
        "Any remaining amount goes to 'Other Expenses / Unallocated'."
    )
)
async def create_budget_plan_endpoint(request: InitialBudgetSetupRequest):
    """
    Create a new budget plan with IST timestamp.
    
    This endpoint:
    1. Creates a new budget plan with the specified total budget
    2. Automatically distributes budget across predefined categories
    3. Returns the complete budget breakdown with IST timestamp
    
    Args:
        request: Budget setup information including reference_id, total_budget, guest_count, etc.
        
    Returns:
        Complete budget plan with IST timestamp and category breakdown
    """
    try:
        logger.info(f"Creating budget plan for reference_id: {request.reference_id}")
        
        # Validate the reference_id
        if not request.reference_id.strip():
            raise HTTPException(
                status_code=400,
                detail="Reference ID cannot be empty."
            )
        
        # Create the budget plan using the service
        budget_plan_db: BudgetPlanDBSchema = create_initial_budget_plan(request)
        
        # ✅ Get current IST timestamp for the API response
        current_timestamp = get_ist_timestamp()
        
        # ✅ Create the API response with proper timestamp
        api_response = BudgetPlannerAPIResponse(
            reference_id=budget_plan_db.reference_id,
            timestamp=current_timestamp,  # Use current IST timestamp
            total_budget=budget_plan_db.current_total_budget,
            budget_breakdown=budget_plan_db.budget_breakdown,
            spent=budget_plan_db.total_spent,
            balance=budget_plan_db.balance,
            selected_vendors=budget_plan_db.selected_vendors
        )
        
        logger.info(f"Budget plan created successfully for {request.reference_id} at {current_timestamp}")
        return api_response
        
    except HTTPException as he:
        # Re-raise HTTP exceptions
        raise he
    except Exception as e:
        logger.error(f"Error creating budget plan for {request.reference_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error creating budget plan.")