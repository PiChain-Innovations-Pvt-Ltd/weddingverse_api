# # app/routers/batch_adjust_router.py
# from fastapi import APIRouter, HTTPException, Depends, Path, Body
# from app.models.budget import (
#     BatchAdjustEstimatesFixedTotalRequest,
#     BudgetPlannerAPIResponse,
#     BudgetPlanDBSchema
# )
# from app.services.batch_adjust_service import process_batch_adjustments_fixed_total
# from app.utils.logger import logger
# from app.dependencies import require_jwt_auth

# router = APIRouter(
#     prefix="/api/v1/budget-planner/{reference_id}",
#     tags=["Budget Planner - Batch Adjustments (Fixed Total)"],
#     dependencies=[Depends(require_jwt_auth)]
# )

# @router.post(
#     "/batch-adjust-fixed-total",
#     response_model=BudgetPlannerAPIResponse,
#     summary="Batch Adjust Categories, Add New Categories & Edit Total Budget",
#     description=(
#         "Comprehensive budget management endpoint that can: "
#         "1. UPDATE existing category estimates "
#         "2. ADD new expense categories "
#         "3. CHANGE the total budget amount "
#         "The new_total_budget field logic: "
#         "- If new_total_budget > 0: Updates budget to this new amount "
#         "- If new_total_budget = 0: Keeps existing budget unchanged "
#         "Untouched categories are adjusted proportionally to fit the target budget. "
#         "New categories are added at the end of the budget breakdown."
#     )
# )
# async def endpoint_batch_adjust_estimates_fixed_total(
#     reference_id: str = Path(..., description="The unique reference ID of the budget plan"),
#     request_body: BatchAdjustEstimatesFixedTotalRequest = Body(
#         ...,
#         examples={
#             "update_existing_keep_budget": {
#                 "summary": "Update existing categories (keep current budget)",
#                 "description": "Set new_total_budget to 0 to maintain existing budget while adjusting categories",
#                 "value": {
#                     "new_total_budget": 0,  # 0 = keep existing budget
#                     "adjustments": [
#                         {"category_name": "Venue", "new_estimate": 350000},
#                         {"category_name": "Photography", "new_estimate": 50000}
#                     ]
#                 }
#             },
#             "add_new_categories_keep_budget": {
#                 "summary": "Add new categories (keep current budget)",
#                 "description": "Set new_total_budget to 0 to maintain existing budget while adding new categories",
#                 "value": {
#                     "new_total_budget": 0,  # 0 = keep existing budget
#                     "adjustments": [
#                         {"category_name": "Photographer", "new_estimate": 80000},
#                         {"category_name": "DJ", "new_estimate": 40000}
#                     ]
#                 }
#             },
#             "change_budget_moderate": {
#                 "summary": "Change budget to moderate amount",
#                 "description": "Set new_total_budget > 0 to update budget and redistribute categories",
#                 "value": {
#                     "new_total_budget": 1500000,  # > 0 = update budget
#                     "adjustments": [
#                         {"category_name": "Venue", "new_estimate": 600000},
#                         {"category_name": "Photography", "new_estimate": 200000}
#                     ]
#                 }
#             },
#             "change_budget_comprehensive": {
#                 "summary": "Increase budget with new categories",
#                 "description": "Significantly increase budget and add multiple new expense categories",
#                 "value": {
#                     "new_total_budget": 2000000,  # > 0 = update budget
#                     "adjustments": [
#                         {"category_name": "Venue", "new_estimate": 800000},
#                         {"category_name": "Caterer", "new_estimate": 500000},
#                         {"category_name": "Photographer", "new_estimate": 180000},
#                         {"category_name": "DJ", "new_estimate": 100000},
#                         {"category_name": "Decorator", "new_estimate": 150000}
#                     ]
#                 }
#             }
#         }
#     )
# ):
#     try:
#         if not request_body.adjustments:
#             raise HTTPException(status_code=400, detail="Adjustments list cannot be empty.")

#         processed_plan: BudgetPlanDBSchema = process_batch_adjustments_fixed_total(
#             reference_id,
#             request_body
#         )

#         api_response = BudgetPlannerAPIResponse(
#             reference_id=processed_plan.reference_id,
#             total_budget=processed_plan.current_total_budget,
#             budget_breakdown=processed_plan.budget_breakdown,
#             spent=processed_plan.total_spent,
#             balance=processed_plan.balance
#         )
#         return api_response
        
#     except HTTPException as he:
#         raise he
#     except Exception as e:
#         logger.error(f"Unexpected error during batch estimate adjustment for plan {reference_id}: {e}", exc_info=True)
#         raise HTTPException(status_code=500, detail="Internal server error during batch estimate adjustment.") 

# app/routers/batch_adjust_router.py
from fastapi import APIRouter, HTTPException, Depends, Path, Body
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

@router.post(
    "/batch-adjust-fixed-total",
    response_model=BudgetPlannerAPIResponse,
    summary="Batch Adjust, Add, Delete Categories & Edit Total Budget",
    description=(
        "Comprehensive budget management endpoint that can: "
        "1. UPDATE existing category estimates "
        "2. ADD new expense categories "
        "3. DELETE existing categories (amounts redistributed to remaining categories) "
        "4. CHANGE the total budget amount "
        "The new_total_budget field logic: "
        "- If new_total_budget > 0: Updates budget to this new amount "
        "- If new_total_budget = 0: Keeps existing budget unchanged "
        "When categories are deleted, their amounts are redistributed proportionally among remaining categories. "
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
                        {"category_name": "Venue", "new_estimate": 15000},
                        {"category_name": "Photography", "new_estimate": 8000}
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
                        {"category_name": "Photographer", "new_estimate": 12000},
                        {"category_name": "Decorator", "new_estimate": 8000}
                    ],
                    "deletions": []
                }
            },
            "delete_categories": {
                "summary": "Delete categories and redistribute amounts",
                "description": "Delete specified categories and redistribute their amounts proportionally among remaining categories",
                "value": {
                    "new_total_budget": 0,
                    "adjustments": [],
                    "deletions": [
                        {"category_name": "DJ"},
                        {"category_name": "Mehendi"}
                    ]
                }
            },
            "delete_all_categories": {
                "summary": "Delete all categories",
                "description": "Delete all categories - entire budget amount goes to balance",
                "value": {
                    "new_total_budget": 0,
                    "adjustments": [],
                    "deletions": [
                        {"category_name": "Venue"},
                        {"category_name": "Caterer"},
                        {"category_name": "Photography"},
                        {"category_name": "Makeup"},
                        {"category_name": "DJ"},
                        {"category_name": "Mehendi"}
                    ]
                }
            },
            "mixed_operations_keep_budget": {
                "summary": "Delete, update, and add categories",
                "description": "Combine deletions, updates, and new additions while keeping existing budget",
                "value": {
                    "new_total_budget": 0,
                    "adjustments": [
                        {"category_name": "Venue", "new_estimate": 15000},
                        {"category_name": "Decorator", "new_estimate": 5000}
                    ],
                    "deletions": [
                        {"category_name": "DJ"},
                        {"category_name": "Mehendi"}
                    ]
                }
            },
            "change_budget_moderate": {
                "summary": "Change budget to moderate amount",
                "description": "Set new_total_budget > 0 to update budget and redistribute categories",
                "value": {
                    "new_total_budget": 50000,
                    "adjustments": [
                        {"category_name": "Venue", "new_estimate": 20000},
                        {"category_name": "Photography", "new_estimate": 15000}
                    ],
                    "deletions": []
                }
            },
            "change_budget_with_deletions": {
                "summary": "Change budget and delete some categories",
                "description": "Update budget amount while deleting categories and adjusting others",
                "value": {
                    "new_total_budget": 40000,
                    "adjustments": [
                        {"category_name": "Venue", "new_estimate": 18000},
                        {"category_name": "Caterer", "new_estimate": 12000}
                    ],
                    "deletions": [
                        {"category_name": "DJ"},
                        {"category_name": "Mehendi"}
                    ]
                }
            },
            "comprehensive_update": {
                "summary": "Complete budget overhaul",
                "description": "Change budget, delete some categories, update existing ones, and add new categories",
                "value": {
                    "new_total_budget": 75000,
                    "adjustments": [
                        {"category_name": "Venue", "new_estimate": 30000},
                        {"category_name": "Caterer", "new_estimate": 20000},
                        {"category_name": "Photographer", "new_estimate": 15000},
                        {"category_name": "Decorator", "new_estimate": 10000}
                    ],
                    "deletions": [
                        {"category_name": "DJ"},
                        {"category_name": "Mehendi"}
                    ]
                }
            },
            "only_deletions": {
                "summary": "Only delete categories",
                "description": "Just delete specific categories without any other changes",
                "value": {
                    "new_total_budget": 0,
                    "adjustments": [],
                    "deletions": [
                        {"category_name": "Makeup"}
                    ]
                }
            },
            "partial_deletion_with_new_budget": {
                "summary": "Delete some categories with new budget",
                "description": "Delete categories and set new budget amount",
                "value": {
                    "new_total_budget": 25000,
                    "adjustments": [],
                    "deletions": [
                        {"category_name": "DJ"},
                        {"category_name": "Mehendi"},
                        {"category_name": "Makeup"}
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

        processed_plan: BudgetPlanDBSchema = process_batch_adjustments_fixed_total(
            reference_id,
            request_body
        )

        api_response = BudgetPlannerAPIResponse(
            reference_id=processed_plan.reference_id,
            total_budget=processed_plan.current_total_budget,
            budget_breakdown=processed_plan.budget_breakdown,
            spent=processed_plan.total_spent,
            balance=processed_plan.balance
        )
        return api_response
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Unexpected error during batch estimate adjustment for plan {reference_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during batch estimate adjustment.")