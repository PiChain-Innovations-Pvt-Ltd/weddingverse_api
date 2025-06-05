# app/routers/budget_retrieval_router.py
from fastapi import APIRouter, HTTPException, Depends, Path
from app.models.budget import BudgetPlannerAPIResponse, BudgetPlanDBSchema
from app.services.mongo_service import db
from app.utils.logger import logger
from app.dependencies import require_jwt_auth

from app.utils.logger import logger

from app.config import settings

BUDGET_PLANS_COLLECTION = settings.BUDGET_PLANS_COLLECTION

router = APIRouter(
    prefix="/api/v1/budget-planner",
    tags=["Budget Planner - Retrieval"],
    dependencies=[Depends(require_jwt_auth)]
)

@router.get(
    "/{reference_id}",
    response_model=BudgetPlannerAPIResponse,
    summary="Get Budget Plan by Reference ID",
    description=(
        "Retrieves the complete budget plan information for a user by their reference_id. "
        "Returns all budget breakdown details, selected vendors, spending information, and plan metadata. "
        "This endpoint is used by the UI to load existing budget plan data."
    )
)
async def get_budget_plan_endpoint(
    reference_id: str = Path(..., description="The unique reference ID of the budget plan to retrieve")
):
    """
    Retrieve a complete budget plan by reference_id.
    
    This endpoint returns:
    - Budget breakdown with categories, estimates, actual costs, payment statuses
    - Selected vendors with all their details and image URLs
    - Total budget, spent amount, and remaining balance
    - Plan metadata like timestamp, location, guest count, etc.
    """
    try:
        logger.info(f"Retrieving budget plan for reference_id: {reference_id}")
        
        # Fetch the budget plan from database
        plan_dict = db[BUDGET_PLANS_COLLECTION].find_one({"reference_id": reference_id})
        
        if not plan_dict:
            logger.warning(f"Budget plan with reference_id '{reference_id}' not found")
            raise HTTPException(
                status_code=404, 
                detail=f"Budget plan with reference_id '{reference_id}' not found."
            )
        
        try:
            # Validate and convert to Pydantic model
            plan = BudgetPlanDBSchema.model_validate(plan_dict)
        except Exception as e:
            logger.error(f"Data validation error for budget plan {reference_id}: {e}")
            raise HTTPException(
                status_code=500, 
                detail="Error validating budget plan data from database."
            )
        
        # Convert to API response format
        api_response = BudgetPlannerAPIResponse(
            reference_id=plan.reference_id,
            timestamp=plan.timestamp,
            total_budget=plan.current_total_budget,
            budget_breakdown=plan.budget_breakdown,
            spent=plan.total_spent,
            balance=plan.balance,
            selected_vendors=plan.selected_vendors
        )
        
        logger.info(f"Successfully retrieved budget plan for reference_id: {reference_id}")
        return api_response
        
    except HTTPException as he:
        # Re-raise HTTP exceptions (like 404)
        raise he
    except Exception as e:
        logger.error(f"Unexpected error retrieving budget plan for reference_id {reference_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail="Internal server error while retrieving budget plan."
        )