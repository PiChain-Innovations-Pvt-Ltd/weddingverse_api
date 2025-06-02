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
#     summary="Batch Adjust, Add, Delete Categories & Edit Total Budget",
#     description=(
#         "Comprehensive budget management endpoint that can: "
#         "1. UPDATE existing category estimates, actual costs, and payment statuses. "
#         "2. ADD new expense categories with initial estimates, actual costs, and payment statuses. "
#         "3. DELETE existing categories (estimates redistributed to remaining categories). "
#         "4. CHANGE the total budget amount. "
#         "The new_total_budget field logic: "
#         "- If new_total_budget > 0: Updates budget to this new amount. "
#         "- If new_total_budget = 0: Keeps existing budget unchanged. "
#         "When categories are deleted, their estimates are redistributed proportionally among remaining categories. "
#         "If all categories are deleted, the full budget amount goes to balance. "
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
#                     "new_total_budget": 0,
#                     "adjustments": [
#                         {"category_name": "Venue", "estimate": 15000, "actual_cost": 10000, "payment_status": "Partially Paid"},
#                         {"category_name": "Photography", "estimate": 8000, "actual_cost": 8000, "payment_status": "Paid"}
#                     ],
#                     "deletions": []
#                 }
#             },
#             "add_new_categories_keep_budget": {
#                 "summary": "Add new categories (keep current budget)",
#                 "description": "Set new_total_budget to 0 to maintain existing budget while adding new categories",
#                 "value": {
#                     "new_total_budget": 0,
#                     "adjustments": [
#                         {"category_name": "Videographer", "estimate": 12000, "actual_cost": 0, "payment_status": "Not Paid"},
#                         {"category_name": "Favors", "estimate": 8000, "actual_cost": 8000, "payment_status": "Paid"}
#                     ],
#                     "deletions": []
#                 }
#             },
#             "delete_categories": {
#                 "summary": "Delete categories and redistribute amounts",
#                 "description": "Delete specified categories and redistribute their estimates proportionally among remaining categories",
#                 "value": {
#                     "new_total_budget": 0,
#                     "adjustments": [],
#                     "deletions": [
#                         {"category_name": "DJ"},
#                         {"category_name": "Mehendi"}
#                     ]
#                 }
#             },
#             "delete_all_categories": {
#                 "summary": "Delete all categories",
#                 "description": "Delete all categories - entire budget amount goes to balance. Total spent becomes 0.",
#                 "value": {
#                     "new_total_budget": 0,
#                     "adjustments": [],
#                     "deletions": [
#                         {"category_name": "Venue"},
#                         {"category_name": "Caterer"},
#                         {"category_name": "Photography"},
#                         {"category_name": "Makeup"},
#                         {"category_name": "DJ"},
#                         {"category_name": "Mehendi"}
#                     ]
#                 }
#             },
#             "mixed_operations_keep_budget": {
#                 "summary": "Delete, update, and add categories (keep current budget)",
#                 "description": "Combine deletions, updates (with actual_cost/status), and new additions while keeping existing budget",
#                 "value": {
#                     "new_total_budget": 0,
#                     "adjustments": [
#                         {"category_name": "Venue", "estimate": 15000, "actual_cost": 14000, "payment_status": "Paid"},
#                         {"category_name": "Decorator", "estimate": 5000, "actual_cost": 2000, "payment_status": "Partially Paid"}
#                     ],
#                     "deletions": [
#                         {"category_name": "DJ"},
#                         {"category_name": "Mehendi"}
#                     ]
#                 }
#             },
#             "change_budget_moderate": {
#                 "summary": "Change budget to moderate amount",
#                 "description": "Set new_total_budget > 0 to update budget and redistribute categories",
#                 "value": {
#                     "new_total_budget": 50000,
#                     "adjustments": [
#                         {"category_name": "Venue", "estimate": 20000, "actual_cost": 18000, "payment_status": "Paid"},
#                         {"category_name": "Photography", "estimate": 15000, "actual_cost": 10000, "payment_status": "Partially Paid"}
#                     ],
#                     "deletions": []
#                 }
#             },
#             "change_budget_with_deletions": {
#                 "summary": "Change budget and delete some categories",
#                 "description": "Update budget amount while deleting categories and adjusting others",
#                 "value": {
#                     "new_total_budget": 40000,
#                     "adjustments": [
#                         {"category_name": "Venue", "estimate": 18000, "actual_cost": 18000, "payment_status": "Paid"},
#                         {"category_name": "Caterer", "estimate": 12000, "actual_cost": 10000, "payment_status": "Partially Paid"}
#                     ],
#                     "deletions": [
#                         {"category_name": "DJ"},
#                         {"category_name": "Mehendi"}
#                     ]
#                 }
#             },
#             "comprehensive_update": {
#                 "summary": "Complete budget overhaul",
#                 "description": "Change budget, delete some categories, update existing ones (with actual_cost/status), and add new categories",
#                 "value": {
#                     "new_total_budget": 75000,
#                     "adjustments": [
#                         {"category_name": "Venue", "estimate": 30000, "actual_cost": 30000, "payment_status": "Paid"},
#                         {"category_name": "Caterer", "estimate": 20000, "actual_cost": 15000, "payment_status": "Partially Paid"},
#                         {"category_name": "Photographer", "estimate": 15000, "actual_cost": 15000, "payment_status": "Paid"},
#                         {"category_name": "Decorator", "estimate": 10000, "actual_cost": 0, "payment_status": "Not Paid"},
#                         {"category_name": "Wedding Planner", "estimate": 8000, "actual_cost": 8000, "payment_status": "Paid"} # New category
#                     ],
#                     "deletions": [
#                         {"category_name": "DJ"},
#                         {"category_name": "Mehendi"}
#                     ]
#                 }
#             },
#             "only_deletions": {
#                 "summary": "Only delete categories",
#                 "description": "Just delete specific categories without any other changes",
#                 "value": {
#                     "new_total_budget": 0,
#                     "adjustments": [],
#                     "deletions": [
#                         {"category_name": "Makeup"}
#                     ]
#                 }
#             },
#             "partial_deletion_with_new_budget": {
#                 "summary": "Delete some categories with new budget",
#                 "description": "Delete categories and set new budget amount",
#                 "value": {
#                     "new_total_budget": 25000,
#                     "adjustments": [],
#                     "deletions": [
#                         {"category_name": "DJ"},
#                         {"category_name": "Mehendi"},
#                         {"category_name": "Makeup"}
#                     ]
#                 }
#             },
#             "adjustments_only_actual_cost_status": {
#                 "summary": "Adjust only actual cost and payment status (keeping existing estimate)",
#                 "description": "Update actual cost and payment status for existing categories without changing estimates or total budget. If estimate is 0 in request, it implies no change to estimate.",
#                 "value": {
#                     "new_total_budget": 0,
#                     "adjustments": [
#                         {"category_name": "Venue", "estimate": 0, "actual_cost": 16000, "payment_status": "Paid"},
#                         {"category_name": "Photography", "estimate": 0, "actual_cost": 5000, "payment_status": "Partially Paid"}
#                     ],
#                     "deletions": []
#                 }
#             }
#         }
#     )
# ):
#     try:
#         # Check if there are any operations to perform
#         has_adjustments = bool(request_body.adjustments)
#         has_deletions = bool(request_body.deletions)
#         has_budget_change = request_body.new_total_budget > 0
        
#         if not has_adjustments and not has_deletions and not has_budget_change:
#             raise HTTPException(
#                 status_code=400, 
#                 detail="No operations specified. Please provide adjustments, deletions, or a new budget amount."
#             )

#         processed_plan: BudgetPlanDBSchema = process_batch_adjustments_fixed_total(
#             reference_id,
#             request_body
#         )

#         api_response = BudgetPlannerAPIResponse(
#             reference_id=processed_plan.reference_id,
#             total_budget=processed_plan.current_total_budget,
#             budget_breakdown=processed_plan.budget_breakdown,
#             spent=processed_plan.total_spent, # This is the total spent
#             balance=processed_plan.balance
#         )
#         return api_response
        
#     except HTTPException as he:
#         raise he
#     except Exception as e:
#         logger.error(f"Unexpected error during batch estimate adjustment for plan {reference_id}: {e}", exc_info=True)
#         raise HTTPException(status_code=500, detail="Internal server error during batch estimate adjustment.")




# # app/routers/batch_adjust_router.py
# from fastapi import APIRouter, HTTPException, Depends, Path, Body
# from app.models.budget import (
#     BatchAdjustEstimatesFixedTotalRequest, # Using the model that includes deletions and new_total_budget
#     BudgetPlannerAPIResponse,
#     BudgetPlanDBSchema
# )
# from app.services.batch_adjust_service import process_batch_adjustments_fixed_total # Assuming this is the correct service function
# from app.utils.logger import logger
# from app.dependencies import require_jwt_auth

# router = APIRouter(
#     prefix="/api/v1/budget-planner/{reference_id}",
#     tags=["Budget Planner - Customise Plan"], # Updated tag for clarity
#     dependencies=[Depends(require_jwt_auth)]
# )

# @router.post(
#     "/customise-plan", # Path updated to reflect more general customisation
#     response_model=BudgetPlannerAPIResponse,
#     summary="Customise Budget Plan (Overall Budget, Category Estimates, Add/Delete Categories)",
#     description=(
#         "Comprehensive budget management endpoint that can: "
#         "1. UPDATE existing category estimates, actual costs, and payment statuses. "
#         "2. ADD new expense categories. "
#         "3. DELETE existing categories. "
#         "4. CHANGE the overall total budget amount. "
#         "If 'new_total_budget' is > 0, it becomes the plan's new target total. Category estimates are then adjusted/redistributed to meet this total. "
#         "If 'new_total_budget' is 0 or not provided, the plan's existing total budget is maintained (if possible given other adjustments)."
#     ),
#     examples={ # Using the 'examples' key for multiple examples in OpenAPI 3.1+
#             "update_categories_keep_total": {
#                 "summary": "Update categories, keep current total",
#                 "value": {
#                     "new_total_budget": 0,
#                     "adjustments": [
#                         {"category_name": "Venue", "new_estimate": 350000, "actual_cost": 340000, "payment_status": "Partially Paid"},
#                         {"category_name": "Photography", "new_estimate": 150000, "actual_cost": 150000, "payment_status": "Paid"}
#                     ],
#                     "deletions": []
#                 }
#             },
#             "add_and_delete_change_total": {
#                 "summary": "Add, delete categories, and change total budget",
#                 "value": {
#                     "new_total_budget": 1800000,
#                     "adjustments": [
#                         {"category_name": "Venue", "new_estimate": 700000},
#                         {"category_name": "Decorations", "new_estimate": 200000} # New category
#                     ],
#                     "deletions": [
#                         {"category_name": "Makeup"}
#                     ]
#                 }
#             },
#             "only_change_total_budget": {
#                 "summary": "Only change the overall total budget",
#                 "value": {
#                     "new_total_budget": 1600000,
#                     "adjustments": [],
#                     "deletions": []
#                 }
#             }
#         }
# )
# async def endpoint_customise_budget_plan(
#     reference_id: str = Path(..., description="The unique reference ID of the budget plan"),
#     request_body: BatchAdjustEstimatesFixedTotalRequest = Body(...)
# ):
#     try:
#         has_adjustments = bool(request_body.adjustments)
#         has_deletions = bool(request_body.deletions)
#         has_budget_change = request_body.new_total_budget is not None and request_body.new_total_budget > 0
        
#         if not has_adjustments and not has_deletions and not has_budget_change:
#             raise HTTPException(
#                 status_code=400, 
#                 detail="No operations specified. Please provide adjustments, deletions, or a new_total_budget > 0."
#             )

#         processed_plan: BudgetPlanDBSchema = process_batch_adjustments_fixed_total( # Ensure this service function name matches
#             reference_id,
#             request_body
#         )

#         api_response = BudgetPlannerAPIResponse(
#             reference_id=processed_plan.reference_id,
#             timestamp=processed_plan.timestamp, # <-- MODIFIED: Added timestamp
#             total_budget=processed_plan.current_total_budget,
#             budget_breakdown=processed_plan.budget_breakdown,
#             spent=processed_plan.total_spent,
#             balance=processed_plan.balance
#         )
#         return api_response
        
#     except HTTPException as he:
#         raise he
#     except Exception as e:
#         logger.error(f"Unexpected error during budget customisation for plan {reference_id}: {e}", exc_info=True)
#         raise HTTPException(status_code=500, detail="Internal server error during budget customisation.") 




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
                        {"category_name": "Venue", "estimate": 15000, "actual_cost": 10000, "payment_status": "Partially Paid"},
                        {"category_name": "Photography", "estimate": 8000, "actual_cost": 8000, "payment_status": "Paid"}
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
                        {"category_name": "Videographer", "estimate": 12000, "actual_cost": 0, "payment_status": "Not Paid"},
                        {"category_name": "Favors", "estimate": 8000, "actual_cost": 8000, "payment_status": "Paid"}
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
            "delete_all_categories": {
                "summary": "Delete all categories",
                "description": "Delete all categories - entire budget amount goes to balance. Total spent becomes 0.",
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
                "summary": "Delete, update, and add categories (keep current budget)",
                "description": "Combine deletions, updates (with actual_cost/status), and new additions while keeping existing budget",
                "value": {
                    "new_total_budget": 0,
                    "adjustments": [
                        {"category_name": "Venue", "estimate": 15000, "actual_cost": 14000, "payment_status": "Paid"},
                        {"category_name": "Decorator", "estimate": 5000, "actual_cost": 2000, "payment_status": "Partially Paid"}
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
                        {"category_name": "Venue", "estimate": 20000, "actual_cost": 18000, "payment_status": "Paid"},
                        {"category_name": "Photography", "estimate": 15000, "actual_cost": 10000, "payment_status": "Partially Paid"}
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
                        {"category_name": "Venue", "estimate": 18000, "actual_cost": 18000, "payment_status": "Paid"},
                        {"category_name": "Caterer", "estimate": 12000, "actual_cost": 10000, "payment_status": "Partially Paid"}
                    ],
                    "deletions": [
                        {"category_name": "DJ"},
                        {"category_name": "Mehendi"}
                    ]
                }
            },
            "comprehensive_update": {
                "summary": "Complete budget overhaul",
                "description": "Change budget, delete some categories, update existing ones (with actual_cost/status), and add new categories",
                "value": {
                    "new_total_budget": 75000,
                    "adjustments": [
                        {"category_name": "Venue", "estimate": 30000, "actual_cost": 30000, "payment_status": "Paid"},
                        {"category_name": "Caterer", "estimate": 20000, "actual_cost": 15000, "payment_status": "Partially Paid"},
                        {"category_name": "Photographer", "estimate": 15000, "actual_cost": 15000, "payment_status": "Paid"},
                        {"category_name": "Decorator", "estimate": 10000, "actual_cost": 0, "payment_status": "Not Paid"},
                        {"category_name": "Wedding Planner", "estimate": 8000, "actual_cost": 8000, "payment_status": "Paid"} # New category
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
            },
            "adjustments_only_actual_cost_status": {
                "summary": "Adjust only actual cost and payment status (keeping existing estimate)",
                "description": "Update actual cost and payment status for existing categories without changing estimates or total budget. If estimate is 0 in request, it implies no change to estimate.",
                "value": {
                    "new_total_budget": 0,
                    "adjustments": [
                        {"category_name": "Venue", "estimate": 0, "actual_cost": 16000, "payment_status": "Paid"},
                        {"category_name": "Photography", "estimate": 0, "actual_cost": 5000, "payment_status": "Partially Paid"}
                    ],
                    "deletions": []
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
            spent=processed_plan.total_spent, # This is the total spent
            balance=processed_plan.balance
        )
        return api_response
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Unexpected error during batch estimate adjustment for plan {reference_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during batch estimate adjustment.")