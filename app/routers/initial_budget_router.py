# app/routers/initial_budget_router.py
from fastapi import APIRouter, HTTPException, Depends
from app.models.budget import InitialBudgetSetupRequest, BudgetPlannerAPIResponse, BudgetPlanDBSchema
from app.services.budget_service import create_initial_budget_plan
from app.utils.logger import logger
from app.dependencies import require_jwt_auth

router = APIRouter(
    prefix="/api/v1",
    tags=["Budget Planner - Initial Setup"],
    dependencies=[Depends(require_jwt_auth)]
)

@router.post(
    "/budget-planner",
    response_model=BudgetPlannerAPIResponse,
    summary="Create or Update an Initial Wedding Budget Plan",
    description=(
        "Takes total budget, guest count, location, dates, and number of events "
        "to provide an initial budget breakdown. If a plan for the given reference_id "
        "already exists, its breakdown and metadata are overwritten by this new initial setup."
    )
)
async def create_budget_plan_endpoint(request: InitialBudgetSetupRequest):
    try:
        if not request.reference_id.strip():
            raise ValueError("reference_id cannot be empty.")
        if not request.location.strip():
            raise ValueError("location cannot be empty.")

        full_budget_plan: BudgetPlanDBSchema = create_initial_budget_plan(request)

        # Explicitly construct the BudgetPlannerAPIResponse
        api_response = BudgetPlannerAPIResponse(
            reference_id=full_budget_plan.reference_id,
            timestamp=full_budget_plan.timestamp,  # <-- MODIFIED: Added timestamp
            total_budget=full_budget_plan.current_total_budget,
            budget_breakdown=full_budget_plan.budget_breakdown,
            spent=full_budget_plan.total_spent,
            balance=full_budget_plan.balance
        )
        return api_response
        
    except ValueError as ve:
        logger.warning(f"Validation error during budget plan creation for {request.reference_id}: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Unexpected error creating budget plan for reference_id {request.reference_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal server error occurred while processing the budget plan.")