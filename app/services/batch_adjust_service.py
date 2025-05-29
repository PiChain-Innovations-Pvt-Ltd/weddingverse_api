# # app/services/batch_adjust_service.py
# from datetime import datetime, timezone
# from typing import List, Dict
# from fastapi import HTTPException, status
# from app.models.budget import (
#     BudgetPlanDBSchema,
#     BudgetCategoryBreakdown,
#     BatchAdjustEstimatesFixedTotalRequest
# )
# from app.services.mongo_service import db
# from app.utils.logger import logger

# BUDGET_PLANS_COLLECTION = "budget_plans"
# REMAINING_BUDGET_CATEGORY_NAME = "Other Expenses / Unallocated"

# def process_batch_adjustments_fixed_total(
#     reference_id: str,
#     request_data: BatchAdjustEstimatesFixedTotalRequest
# ) -> BudgetPlanDBSchema:
#     logger.info(f"Processing batch estimate adjustments for plan_id: {reference_id}")

#     plan_dict = db[BUDGET_PLANS_COLLECTION].find_one({"_id": reference_id})
#     if not plan_dict:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Budget plan with reference_id '{reference_id}' not found.")

#     try:
#         plan = BudgetPlanDBSchema.model_validate(plan_dict)
#     except Exception as e:
#         logger.error(f"Data validation error for existing plan {reference_id}: {e}")
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error validating existing budget plan data.")

#     # Use new budget only if it's greater than 0, otherwise keep existing budget
#     if request_data.new_total_budget > 0:
#         target_total_budget = request_data.new_total_budget
#         budget_was_changed = True
#         logger.info(f"Budget updated from {plan.current_total_budget} to {target_total_budget}")
#     else:
#         target_total_budget = plan.current_total_budget
#         budget_was_changed = False
#         logger.info(f"Using existing budget: {target_total_budget} (new_total_budget was {request_data.new_total_budget})")

#     working_estimates: Dict[str, float] = {cat.category_name: cat.estimated_amount for cat in plan.budget_breakdown}
    
#     sum_of_newly_set_estimates = 0.0
#     categories_in_batch_adjustment = set()
#     new_categories_to_add = []

#     for adj_item in request_data.adjustments:
#         adj_item.new_estimate = round(adj_item.new_estimate, 2)
        
#         # Only process adjustments where new_estimate > 0
#         if adj_item.new_estimate <= 0:
#             logger.info(f"Skipping category '{adj_item.category_name}' with estimate {adj_item.new_estimate} (must be > 0)")
#             continue
        
#         # Check if this is a new category (not in existing budget)
#         if adj_item.category_name not in working_estimates:
#             # This is a new category to be added
#             new_categories_to_add.append(adj_item)
#             working_estimates[adj_item.category_name] = adj_item.new_estimate
#             logger.info(f"Adding new category: '{adj_item.category_name}' with estimate: {adj_item.new_estimate}")
#         else:
#             # This is an existing category being updated
#             working_estimates[adj_item.category_name] = adj_item.new_estimate
#             logger.info(f"Updating existing category: '{adj_item.category_name}' to estimate: {adj_item.new_estimate}")
        
#         sum_of_newly_set_estimates += adj_item.new_estimate
#         categories_in_batch_adjustment.add(adj_item.category_name)

#     # Check if any valid adjustments were processed
#     if not categories_in_batch_adjustment:
#         logger.warning("No valid adjustments found (all estimates were <= 0). No changes made.")
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST, 
#             detail="No valid adjustments found. All category estimates must be greater than 0."
#         )
#     untouched_categories_data: List[Dict[str, any]] = []
#     sum_of_original_untouched_estimates = 0.0
    
#     # Get untouched categories
#     for cat_in_plan in plan.budget_breakdown:
#         if cat_in_plan.category_name not in categories_in_batch_adjustment:
#             untouched_categories_data.append({"name": cat_in_plan.category_name, "original_estimate": cat_in_plan.estimated_amount})
#             sum_of_original_untouched_estimates += cat_in_plan.estimated_amount

#     required_sum_for_untouched = round(target_total_budget - sum_of_newly_set_estimates, 2)

#     # Handle different scenarios
#     if not untouched_categories_data:
#         # All categories were specified
#         if budget_was_changed:
#             logger.info(f"All categories specified with new budget: {target_total_budget}")
#         else:
#             logger.info(f"All categories adjusted. New total: {sum_of_newly_set_estimates:.2f}, Target budget: {target_total_budget:.2f}")
#     elif required_sum_for_untouched < 0:
#         # Estimates exceed budget - keep untouched categories at their original values
#         logger.warning(f"Estimates ({sum_of_newly_set_estimates:.2f}) exceed target budget ({target_total_budget:.2f}). Maintaining original estimates for untouched categories.")
#         # Don't change untouched categories - they keep their original estimates
#         # working_estimates already has their original values, so no changes needed
#     else:
#         # Distribute remaining budget to untouched categories
#         if sum_of_original_untouched_estimates > 0:
#             # Proportional distribution
#             for cat_data in untouched_categories_data:
#                 proportion = cat_data["original_estimate"] / sum_of_original_untouched_estimates
#                 new_val = round(required_sum_for_untouched * proportion, 2)
#                 working_estimates[cat_data["name"]] = max(new_val, 0.0)
#         elif required_sum_for_untouched > 0:
#             # Equal distribution when original sum was 0
#             amount_per_untouched = round(required_sum_for_untouched / len(untouched_categories_data), 2)
#             for cat_data in untouched_categories_data:
#                 working_estimates[cat_data["name"]] = max(amount_per_untouched, 0.0)

#     # Reconstruct budget breakdown
#     new_breakdown: List[BudgetCategoryBreakdown] = []
    
#     # Add existing categories in original order
#     for original_cat_in_plan in plan.budget_breakdown:
#         cat_name = original_cat_in_plan.category_name
#         estimate = working_estimates.get(cat_name, 0.0)
#         new_breakdown.append(
#             BudgetCategoryBreakdown(category_name=cat_name, estimated_amount=estimate, percentage=0.0)
#         )
    
#     # Add new categories at the end
#     for new_cat in new_categories_to_add:
#         new_breakdown.append(
#             BudgetCategoryBreakdown(
#                 category_name=new_cat.category_name, 
#                 estimated_amount=new_cat.new_estimate, 
#                 percentage=0.0
#             )
#         )

#     # Update plan with new data
#     plan.budget_breakdown = new_breakdown
#     plan.current_total_budget = target_total_budget

#     # Calculate percentages based on the target budget
#     if target_total_budget > 0:
#         for cat_item in plan.budget_breakdown:
#             cat_item.percentage = round((cat_item.estimated_amount / target_total_budget) * 100, 2)
#     else:
#         for cat_item in plan.budget_breakdown:
#             cat_item.percentage = 0.0

#     # Calculate spent and balance
#     spent = round(sum(cat.estimated_amount for cat in plan.budget_breakdown), 2)
#     balance = round(target_total_budget - spent, 2)

#     plan.total_spent = spent
#     plan.balance = balance

#     # Log results
#     if balance < 0:
#         logger.warning(f"Budget exceeded by: {abs(balance)}. Total budget: {target_total_budget}, Total spent: {spent}")
#     elif balance > 0:
#         logger.info(f"Remaining budget: {balance}. Total budget: {target_total_budget}, Total spent: {spent}")
#     else:
#         logger.info(f"Budget perfectly balanced. Total budget: {target_total_budget}, Total spent: {spent}")

#     if new_categories_to_add:
#         logger.info(f"Added {len(new_categories_to_add)} new categories: {[cat.category_name for cat in new_categories_to_add]}")

#     plan.timestamp = datetime.now(timezone.utc)

#     # Save to database
#     document_to_db = {
#         "_id": reference_id,
#         "total_budget_input": plan.total_budget_input,
#         "wedding_dates_input": plan.wedding_dates_input,
#         "guest_count_input": plan.guest_count_input,
#         "location_input": plan.location_input,
#         "no_of_events_input": plan.no_of_events_input,
#         "budget_breakdown": [cat.model_dump() for cat in plan.budget_breakdown],
#         "current_total_budget": plan.current_total_budget,
#         "total_spent": plan.total_spent,
#         "balance": plan.balance,
#         "timestamp": plan.timestamp
#     }
    
#     try:
#         db[BUDGET_PLANS_COLLECTION].update_one({"_id": reference_id}, {"$set": document_to_db})
#         logger.info(f"Budget plan processed for _id: {reference_id}")
#     except Exception as e:
#         logger.error(f"Error saving budget plan for _id: {reference_id} to DB: {e}", exc_info=True)
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save budget plan.")

#     return plan 



# def process_batch_adjustments_fixed_total(
#     reference_id: str,
#     request_data: BatchAdjustEstimatesFixedTotalRequest
# ) -> BudgetPlanDBSchema:
#     logger.info(f"Processing batch estimate adjustments for plan_id: {reference_id}")

#     plan_dict = db[BUDGET_PLANS_COLLECTION].find_one({"_id": reference_id})
#     if not plan_dict:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Budget plan with reference_id '{reference_id}' not found.")

#     try:
#         plan = BudgetPlanDBSchema.model_validate(plan_dict)
#     except Exception as e:
#         logger.error(f"Data validation error for existing plan {reference_id}: {e}")
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error validating existing budget plan data.")

#     # Use new budget only if it's greater than 0, otherwise keep existing budget
#     if request_data.new_total_budget > 0:
#         target_total_budget = request_data.new_total_budget
#         budget_was_changed = True
#         logger.info(f"Budget updated from {plan.current_total_budget} to {target_total_budget}")
#     else:
#         target_total_budget = plan.current_total_budget
#         budget_was_changed = False
#         logger.info(f"Using existing budget: {target_total_budget} (new_total_budget was {request_data.new_total_budget})")

#     working_estimates: Dict[str, float] = {cat.category_name: cat.estimated_amount for cat in plan.budget_breakdown}
    
#     # Process deletions first
#     categories_to_delete = set()
#     total_deleted_amount = 0.0
    
#     # for del_item in request_data.deletions:
#     #     if del_item.category_name in working_estimates:
#     #         categories_to_delete.add(del_item.category_name)
#     #         total_deleted_amount += working_estimates[del_item.category_name]
#     #         logger.info(f"Marking category '{del_item.category_name}' for deletion (amount: {working_estimates[del_item.category_name]})")
#     #     else:
#     #         logger.warning(f"Category '{del_item.category_name}' not found for deletion")
    
#     for del_item in request_data.deletions:
#         # Skip placeholder/example values
#         if del_item.category_name.lower() in ["string", "example", "placeholder", "test"]:
#             logger.info(f"Skipping placeholder deletion category name: '{del_item.category_name}'")
#             continue
            
#         if del_item.category_name in working_estimates:
#             categories_to_delete.add(del_item.category_name)
#             total_deleted_amount += working_estimates[del_item.category_name]
#             logger.info(f"Marking category '{del_item.category_name}' for deletion (amount: {working_estimates[del_item.category_name]})")
#         else:
#             logger.warning(f"Category '{del_item.category_name}' not found for deletion")
        
#     # Remove deleted categories from working estimates
#     for cat_name in categories_to_delete:
#         del working_estimates[cat_name]
    
#     # Process adjustments
#     sum_of_newly_set_estimates = 0.0
#     categories_in_batch_adjustment = set()
#     new_categories_to_add = []

#     # for adj_item in request_data.adjustments:
#     #     adj_item.new_estimate = round(adj_item.new_estimate, 2)
        
#     #     # Only process adjustments where new_estimate > 0
#     #     if adj_item.new_estimate <= 0:
#     #         logger.info(f"Skipping category '{adj_item.category_name}' with estimate {adj_item.new_estimate} (must be > 0)")
#     #         continue
        
#     #     # Skip if category is marked for deletion
#     #     if adj_item.category_name in categories_to_delete:
#     #         logger.warning(f"Skipping adjustment for '{adj_item.category_name}' as it's marked for deletion")
#     #         continue
    
#     for adj_item in request_data.adjustments:
#         adj_item.new_estimate = round(adj_item.new_estimate, 2)
        
#         # Skip placeholder/example values
#         if adj_item.category_name.lower() in ["string", "example", "placeholder", "test"]:
#             logger.info(f"Skipping placeholder category name: '{adj_item.category_name}'")
#             continue
        
#         # Only process adjustments where new_estimate > 0
#         if adj_item.new_estimate <= 0:
#             logger.info(f"Skipping category '{adj_item.category_name}' with estimate {adj_item.new_estimate} (must be > 0)")
#             continue
        
#         # Check if this is a new category (not in existing budget)
#         if adj_item.category_name not in working_estimates:
#             # This is a new category to be added
#             new_categories_to_add.append(adj_item)
#             working_estimates[adj_item.category_name] = adj_item.new_estimate
#             logger.info(f"Adding new category: '{adj_item.category_name}' with estimate: {adj_item.new_estimate}")
#         else:
#             # This is an existing category being updated
#             working_estimates[adj_item.category_name] = adj_item.new_estimate
#             logger.info(f"Updating existing category: '{adj_item.category_name}' to estimate: {adj_item.new_estimate}")
        
#         sum_of_newly_set_estimates += adj_item.new_estimate
#         categories_in_batch_adjustment.add(adj_item.category_name)

#     # Check if we have any categories left
#     if not working_estimates:
#         logger.info("All categories were deleted. Setting balance to total budget.")
#         # Create empty budget with full balance
#         plan.budget_breakdown = []
#         plan.current_total_budget = target_total_budget
#         plan.total_spent = 0.0
#         plan.balance = target_total_budget
#         plan.timestamp = datetime.now(timezone.utc)
        
#         # Save to database
#         document_to_db = {
#             "_id": reference_id,
#             "total_budget_input": plan.total_budget_input,
#             "wedding_dates_input": plan.wedding_dates_input,
#             "guest_count_input": plan.guest_count_input,
#             "location_input": plan.location_input,
#             "no_of_events_input": plan.no_of_events_input,
#             "budget_breakdown": [],
#             "current_total_budget": plan.current_total_budget,
#             "total_spent": plan.total_spent,
#             "balance": plan.balance,
#             "timestamp": plan.timestamp
#         }
        
#         try:
#             db[BUDGET_PLANS_COLLECTION].update_one({"_id": reference_id}, {"$set": document_to_db})
#             logger.info(f"All categories deleted. Budget plan updated for _id: {reference_id}")
#         except Exception as e:
#             logger.error(f"Error saving budget plan for _id: {reference_id} to DB: {e}", exc_info=True)
#             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save budget plan.")
        
#         return plan

#     # Check if any valid adjustments were processed (if no adjustments but have deletions, continue)
#     # if not categories_in_batch_adjustment and not categories_to_delete:
#     #     logger.warning("No valid adjustments or deletions found.")
#     #     raise HTTPException(
#     #         status_code=status.HTTP_400_BAD_REQUEST, 
#     #         detail="No valid adjustments or deletions found. All category estimates must be greater than 0."
#     #     )
    
#     # Check if any valid operations were processed
#     if not categories_in_batch_adjustment and not categories_to_delete and request_data.new_total_budget <= 0:
#         logger.info("No valid operations found. Returning existing budget unchanged.")
#         # Return the existing plan without any changes
#         return plan

#     untouched_categories_data: List[Dict[str, any]] = []
#     sum_of_original_untouched_estimates = 0.0
    
#     # Get untouched categories (not adjusted, not deleted)
#     for cat_in_plan in plan.budget_breakdown:
#         if (cat_in_plan.category_name not in categories_in_batch_adjustment and 
#             cat_in_plan.category_name not in categories_to_delete):
#             untouched_categories_data.append({"name": cat_in_plan.category_name, "original_estimate": cat_in_plan.estimated_amount})
#             sum_of_original_untouched_estimates += cat_in_plan.estimated_amount

#     # Calculate required sum for untouched categories (including deleted amount redistribution)
#     required_sum_for_untouched = round(target_total_budget - sum_of_newly_set_estimates, 2)

#     # Handle different scenarios
#     if not untouched_categories_data:
#         # All categories were either adjusted or deleted
#         if budget_was_changed:
#             logger.info(f"All categories specified with new budget: {target_total_budget}")
#         else:
#             logger.info(f"All categories adjusted/deleted. New total: {sum_of_newly_set_estimates:.2f}, Target budget: {target_total_budget:.2f}")
#     elif required_sum_for_untouched < 0:
#         # Estimates exceed budget - keep untouched categories at their original values
#         logger.warning(f"Estimates ({sum_of_newly_set_estimates:.2f}) exceed target budget ({target_total_budget:.2f}). Maintaining original estimates for untouched categories.")
#         # Don't change untouched categories - they keep their original estimates
#     else:
#         # Distribute remaining budget (including deleted amounts) to untouched categories
#         if sum_of_original_untouched_estimates > 0:
#             # Proportional distribution
#             for cat_data in untouched_categories_data:
#                 proportion = cat_data["original_estimate"] / sum_of_original_untouched_estimates
#                 new_val = round(required_sum_for_untouched * proportion, 2)
#                 working_estimates[cat_data["name"]] = max(new_val, 0.0)
#                 logger.info(f"Redistributed to '{cat_data['name']}': {working_estimates[cat_data['name']]} (proportion: {proportion:.4f})")
#         elif required_sum_for_untouched > 0:
#             # Equal distribution when original sum was 0
#             amount_per_untouched = round(required_sum_for_untouched / len(untouched_categories_data), 2)
#             for cat_data in untouched_categories_data:
#                 working_estimates[cat_data["name"]] = max(amount_per_untouched, 0.0)
#                 logger.info(f"Equal distribution to '{cat_data['name']}': {working_estimates[cat_data['name']]}")

#     # Reconstruct budget breakdown (exclude deleted categories)
#     new_breakdown: List[BudgetCategoryBreakdown] = []
    
#     # Add existing categories in original order (skip deleted ones)
#     for original_cat_in_plan in plan.budget_breakdown:
#         if original_cat_in_plan.category_name not in categories_to_delete:
#             cat_name = original_cat_in_plan.category_name
#             estimate = working_estimates.get(cat_name, 0.0)
#             new_breakdown.append(
#                 BudgetCategoryBreakdown(category_name=cat_name, estimated_amount=estimate, percentage=0.0)
#             )
    
#     # Add new categories at the end
#     for new_cat in new_categories_to_add:
#         new_breakdown.append(
#             BudgetCategoryBreakdown(
#                 category_name=new_cat.category_name, 
#                 estimated_amount=new_cat.new_estimate, 
#                 percentage=0.0
#             )
#         )

#     # Update plan with new data
#     plan.budget_breakdown = new_breakdown
#     plan.current_total_budget = target_total_budget

#     # Calculate percentages based on the target budget
#     if target_total_budget > 0:
#         for cat_item in plan.budget_breakdown:
#             cat_item.percentage = round((cat_item.estimated_amount / target_total_budget) * 100, 2)
#     else:
#         for cat_item in plan.budget_breakdown:
#             cat_item.percentage = 0.0

#     # Calculate spent and balance
#     spent = round(sum(cat.estimated_amount for cat in plan.budget_breakdown), 2)
#     balance = round(target_total_budget - spent, 2)

#     plan.total_spent = spent
#     plan.balance = balance

#     # Log results
#     if balance < 0:
#         logger.warning(f"Budget exceeded by: {abs(balance)}. Total budget: {target_total_budget}, Total spent: {spent}")
#     elif balance > 0:
#         logger.info(f"Remaining budget: {balance}. Total budget: {target_total_budget}, Total spent: {spent}")
#     else:
#         logger.info(f"Budget perfectly balanced. Total budget: {target_total_budget}, Total spent: {spent}")

#     if categories_to_delete:
#         logger.info(f"Deleted {len(categories_to_delete)} categories: {list(categories_to_delete)} (total amount: {total_deleted_amount})")
#     if new_categories_to_add:
#         logger.info(f"Added {len(new_categories_to_add)} new categories: {[cat.category_name for cat in new_categories_to_add]}")

#     plan.timestamp = datetime.now(timezone.utc)

#     # Save to database
#     document_to_db = {
#         "_id": reference_id,
#         "total_budget_input": plan.total_budget_input,
#         "wedding_dates_input": plan.wedding_dates_input,
#         "guest_count_input": plan.guest_count_input,
#         "location_input": plan.location_input,
#         "no_of_events_input": plan.no_of_events_input,
#         "budget_breakdown": [cat.model_dump() for cat in plan.budget_breakdown],
#         "current_total_budget": plan.current_total_budget,
#         "total_spent": plan.total_spent,
#         "balance": plan.balance,
#         "timestamp": plan.timestamp
#     }
    
#     try:
#         db[BUDGET_PLANS_COLLECTION].update_one({"_id": reference_id}, {"$set": document_to_db})
#         logger.info(f"Budget plan processed for _id: {reference_id}")
#     except Exception as e:
#         logger.error(f"Error saving budget plan for _id: {reference_id} to DB: {e}", exc_info=True)
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save budget plan.")

#     return plan


# # app/services/batch_adjust_service.py
# from datetime import datetime, timezone
# from typing import List, Dict
# from fastapi import HTTPException, status
# from app.models.budget import (
#     BudgetPlanDBSchema,
#     BudgetCategoryBreakdown,
#     BatchAdjustEstimatesFixedTotalRequest # This model now includes 'deletions' and 'new_total_budget'
# )
# from app.services.mongo_service import db
# from app.utils.logger import logger

# BUDGET_PLANS_COLLECTION = "budget_plans"
# REMAINING_BUDGET_CATEGORY_NAME = "Other Expenses / Unallocated"

# def process_batch_adjustments_fixed_total( # Renaming back for clarity of its primary intent
#     reference_id: str,
#     request_data: BatchAdjustEstimatesFixedTotalRequest
# ) -> BudgetPlanDBSchema:
#     logger.info(f"Processing batch adjustments for plan_id: {reference_id}")

#     plan_dict = db[BUDGET_PLANS_COLLECTION].find_one({"_id": reference_id})
#     if not plan_dict:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Budget plan with reference_id '{reference_id}' not found.")

#     try:
#         plan = BudgetPlanDBSchema.model_validate(plan_dict)
#     except Exception as e:
#         logger.error(f"Data validation error for existing plan {reference_id}: {e}")
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error validating existing budget plan data.")

#     # Determine the target total budget
#     if request_data.new_total_budget is not None and request_data.new_total_budget > 0:
#         target_total_budget = round(request_data.new_total_budget, 2)
#         budget_was_changed_by_request = True
#         logger.info(f"Request to change total budget to: {target_total_budget}")
#     else:
#         target_total_budget = plan.current_total_budget # Keep existing if new_total_budget is 0 or not provided
#         budget_was_changed_by_request = False
#         logger.info(f"Keeping existing total budget: {target_total_budget}")

#     # --- Step 1: Initialize working_estimates with current plan & incorporate adjustments/additions ---
#     # This dictionary will hold the state of estimates as we process.
#     working_estimates: Dict[str, float] = {cat.category_name: cat.estimated_amount for cat in plan.budget_breakdown}
    
#     # Keep track of categories explicitly mentioned in adjustments (new or updated)
#     categories_explicitly_adjusted = set()

#     if request_data.adjustments:
#         for adj_item in request_data.adjustments:
#             # Skip placeholder/example values if they are not intended to be actual categories
#             if adj_item.category_name.lower() in ["string", "example", "placeholder", "test"]:
#                 logger.info(f"Skipping placeholder adjustment category name: '{adj_item.category_name}'")
#                 continue

#             adj_estimate = round(adj_item.new_estimate, 2)
#             if adj_estimate < 0: # Estimates cannot be negative
#                 raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Estimate for category '{adj_item.category_name}' cannot be negative.")

#             if adj_item.category_name not in working_estimates:
#                 logger.info(f"New category '{adj_item.category_name}' specified in adjustments with estimate {adj_estimate}.")
#             else:
#                 logger.info(f"Updating category '{adj_item.category_name}' from {working_estimates[adj_item.category_name]} to {adj_estimate}.")
            
#             working_estimates[adj_item.category_name] = adj_estimate
#             categories_explicitly_adjusted.add(adj_item.category_name)

#     # --- Step 2: Process Deletions ---
#     # Deletions should apply to the state *after* potential additions/updates from the adjustments list.
#     deleted_categories_estimates_sum = 0.0
#     final_categories_after_deletion: Dict[str, float] = {}

#     categories_to_be_deleted_names = {del_item.category_name for del_item in request_data.deletions if del_item.category_name.lower() not in ["string", "example", "placeholder", "test"]}

#     for cat_name, estimate in working_estimates.items():
#         if cat_name in categories_to_be_deleted_names:
#             deleted_categories_estimates_sum += estimate
#             logger.info(f"Deleting category '{cat_name}' with current estimate {estimate}.")
#         else:
#             final_categories_after_deletion[cat_name] = estimate
    
#     working_estimates = final_categories_after_deletion # Update working_estimates to reflect deletions

#     if not working_estimates: # All categories were deleted or none existed after adjustments
#         logger.info("All categories have been removed from the plan.")
#         plan.budget_breakdown = []
#         plan.current_total_budget = target_total_budget # The target budget is now all "balance"
#         plan.total_spent = 0.0 # Assuming spent is tied to categories that are now gone
#         plan.balance = target_total_budget
#         plan.timestamp = datetime.now(timezone.utc)
#         # Save and return early
#         document_to_db = plan.model_dump(exclude={"reference_id"})
#         db[BUDGET_PLANS_COLLECTION].update_one({"_id": reference_id}, {"$set": document_to_db})
#         return plan

#     # --- Step 3: Redistribute budget among remaining categories ---
#     # The sum that needs to be distributed among the *remaining* (non-deleted, non-explicitly-adjusted) categories.
#     # Or, if all remaining categories were explicitly adjusted, their sum should match target_total_budget.

#     sum_of_estimates_for_explicitly_adjusted_and_remaining = 0.0
#     categories_not_explicitly_adjusted_but_remaining: Dict[str, float] = {} # name: original_estimate_before_this_call

#     for cat_name, current_estimate in working_estimates.items():
#         if cat_name in categories_explicitly_adjusted:
#             sum_of_estimates_for_explicitly_adjusted_and_remaining += current_estimate
#         else:
#             # Find its original estimate from the plan before any modifications in this call
#             original_cat_obj = next((c for c in plan.budget_breakdown if c.category_name == cat_name), None)
#             original_estimate = original_cat_obj.estimated_amount if original_cat_obj else 0 # Default to 0 if somehow not found (should not happen)
#             categories_not_explicitly_adjusted_but_remaining[cat_name] = original_estimate
#             # We will calculate their new estimates based on redistribution

#     # Amount that needs to be covered by/distributed to categories_not_explicitly_adjusted_but_remaining
#     budget_for_non_adjusted_remaining = round(target_total_budget - sum_of_estimates_for_explicitly_adjusted_and_remaining, 2)

#     if categories_not_explicitly_adjusted_but_remaining:
#         sum_of_original_estimates_of_non_adjusted_remaining = sum(categories_not_explicitly_adjusted_but_remaining.values())

#         if budget_for_non_adjusted_remaining < 0:
#             logger.warning(f"Target budget {target_total_budget} is less than sum of explicitly set/adjusted categories. "
#                            f"Non-adjusted categories will be set to 0.")
#             for cat_name in categories_not_explicitly_adjusted_but_remaining.keys():
#                 working_estimates[cat_name] = 0.0
#         elif sum_of_original_estimates_of_non_adjusted_remaining > 0: # Proportional redistribution
#             for cat_name, original_est in categories_not_explicitly_adjusted_but_remaining.items():
#                 proportion = original_est / sum_of_original_estimates_of_non_adjusted_remaining
#                 new_val = round(budget_for_non_adjusted_remaining * proportion, 2)
#                 working_estimates[cat_name] = max(0.0, new_val)
#         elif budget_for_non_adjusted_remaining > 0: # Equal distribution if original sum was 0
#             amount_per_cat = round(budget_for_non_adjusted_remaining / len(categories_not_explicitly_adjusted_but_remaining), 2)
#             for cat_name in categories_not_explicitly_adjusted_but_remaining.keys():
#                 working_estimates[cat_name] = max(0.0, amount_per_cat)
#         # If budget_for_non_adjusted_remaining is 0, they remain 0 or their original values if sum was 0.
#     elif abs(target_total_budget - sum_of_estimates_for_explicitly_adjusted_and_remaining) > 0.01 * max(1, len(working_estimates)):
#         # All remaining categories were explicitly adjusted, their sum should match the target_total_budget
#         # If budget_was_changed_by_request is false, this implies an inconsistency.
#         # If budget_was_changed_by_request is true, the sum of adjustments defines the new total.
#         if not budget_was_changed_by_request: # User did not provide new_total_budget, but sum of adjustments differs from old total
#              logger.warning(f"All remaining categories were explicitly adjusted. Their sum "
#                            f"({sum_of_estimates_for_explicitly_adjusted_and_remaining:.2f}) "
#                            f"differs from the original fixed total budget ({target_total_budget:.2f}). "
#                            f"The sum of adjustments will become the new total budget.")
#         target_total_budget = sum_of_estimates_for_explicitly_adjusted_and_remaining # Sum of parts defines the whole
#         plan.current_total_budget = target_total_budget


#     # --- Step 4: Finalize breakdown and percentages ---
#     new_breakdown_list: List[BudgetCategoryBreakdown] = []
#     final_calculated_sum = 0.0

#     # Reconstruct breakdown, possibly in a new order if categories were added.
#     # To maintain existing order for non-deleted items:
#     existing_categories_order = [cat.category_name for cat in plan.budget_breakdown if cat.category_name in working_estimates]
#     added_category_names = [name for name in working_estimates.keys() if name not in existing_categories_order]
    
#     final_category_order = existing_categories_order + added_category_names

#     for cat_name in final_category_order:
#         estimate = round(working_estimates.get(cat_name, 0.0), 2)
#         new_breakdown_list.append(
#             BudgetCategoryBreakdown(category_name=cat_name, estimated_amount=estimate, percentage=0.0)
#         )
#         final_calculated_sum += estimate
#     final_calculated_sum = round(final_calculated_sum, 2)

#     # Adjust for rounding to match target_total_budget
#     discrepancy = round(target_total_budget - final_calculated_sum, 2)
#     if abs(discrepancy) >= 0.01 and new_breakdown_list:
#         logger.info(f"Final discrepancy of {discrepancy} to match target total. Adjusting.")
#         # Apply to "Other Expenses / Unallocated" or the largest category that can absorb it
#         adj_target_cat = next((c for c in new_breakdown_list if c.category_name == REMAINING_BUDGET_CATEGORY_NAME), None)
#         if not adj_target_cat:
#             new_breakdown_list.sort(key=lambda x: x.estimated_amount, reverse=True)
#             adj_target_cat = new_breakdown_list[0]

#         if adj_target_cat.estimated_amount + discrepancy >= 0:
#             adj_target_cat.estimated_amount = round(adj_target_cat.estimated_amount + discrepancy, 2)
#         else: # Cannot fully absorb, log warning
#             logger.warning(f"Could not fully apply final discrepancy of {discrepancy} to '{adj_target_cat.category_name}'.")
#             # The actual sum might slightly differ from target_total_budget
#             target_total_budget = round(sum(c.estimated_amount for c in new_breakdown_list), 2)


#     plan.budget_breakdown = new_breakdown_list
#     plan.current_total_budget = target_total_budget # This is the definitive total

#     if plan.current_total_budget > 0:
#         for item in plan.budget_breakdown:
#             item.percentage = round((item.estimated_amount / plan.current_total_budget) * 100, 2)
#     else:
#         for item in plan.budget_breakdown: item.percentage = 0.0

#     plan.balance = round(plan.current_total_budget - plan.total_spent, 2) # total_spent is not changed here
#     plan.timestamp = datetime.now(timezone.utc)

#     document_to_db = plan.model_dump(exclude={"reference_id"})
#     try:
#         db[BUDGET_PLANS_COLLECTION].update_one({"_id": reference_id}, {"$set": document_to_db})
#         logger.info(f"Batch budget adjustments processed for _id: {reference_id}. New total: {plan.current_total_budget}")
#     except Exception as e:
#         logger.error(f"Error saving batch adjusted budget plan for _id: {reference_id} to DB: {e}", exc_info=True)
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save batch adjusted budget plan.")

#     return plan


# # app/services/batch_adjust_service.py
# from datetime import datetime, timezone
# from typing import List, Dict
# from fastapi import HTTPException, status
# from app.models.budget import (
#     BudgetPlanDBSchema,
#     BudgetCategoryBreakdown,
#     BatchAdjustEstimatesFixedTotalRequest # This model includes 'deletions' and 'new_total_budget'
# )
# from app.services.mongo_service import db
# from app.utils.logger import logger

# BUDGET_PLANS_COLLECTION = "budget_plans"
# REMAINING_BUDGET_CATEGORY_NAME = "Other Expenses / Unallocated"

# def process_batch_adjustments_fixed_total(
#     reference_id: str,
#     request_data: BatchAdjustEstimatesFixedTotalRequest
# ) -> BudgetPlanDBSchema:
#     logger.info(f"Processing batch adjustments for plan_id: {reference_id}")

#     plan_dict = db[BUDGET_PLANS_COLLECTION].find_one({"_id": reference_id})
#     if not plan_dict:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Budget plan with reference_id '{reference_id}' not found.")

#     try:
#         plan = BudgetPlanDBSchema.model_validate(plan_dict)
#     except Exception as e:
#         logger.error(f"Data validation error for existing plan {reference_id}: {e}")
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error validating existing budget plan data.")

#     # --- Determine the target total budget for this operation ---
#     if request_data.new_total_budget is not None and request_data.new_total_budget > 0:
#         target_total_budget = round(request_data.new_total_budget, 2)
#         budget_was_explicitly_changed_in_request = True
#         logger.info(f"Request to change total budget to: {target_total_budget}")
#     else:
#         target_total_budget = plan.current_total_budget # Keep existing if new_total_budget is 0 or not provided
#         budget_was_explicitly_changed_in_request = False
#         logger.info(f"Keeping existing total budget: {target_total_budget}")

#     # --- Step 1: Initialize working_estimates with current plan's categories ---
#     working_estimates: Dict[str, float] = {cat.category_name: cat.estimated_amount for cat in plan.budget_breakdown}
    
#     # --- Step 2: Process Deletions ---
#     # Apply deletions to the working_estimates dictionary
#     categories_to_be_deleted_names = {
#         del_item.category_name for del_item in request_data.deletions 
#         if del_item.category_name.lower() not in ["string", "example", "placeholder", "test"] # Skip placeholders
#     }
#     for cat_name in categories_to_be_deleted_names:
#         if cat_name in working_estimates:
#             logger.info(f"Deleting category '{cat_name}' from working estimates.")
#             del working_estimates[cat_name]
#         else:
#             logger.warning(f"Category '{cat_name}' requested for deletion not found in current plan estimates.")

#     # --- Step 3: Process Adjustments (Updates and Additions) ---
#     # Apply adjustments to working_estimates. New categories will be added.
#     categories_explicitly_adjusted_or_added = set()
#     if request_data.adjustments:
#         for adj_item in request_data.adjustments:
#             if adj_item.category_name.lower() in ["string", "example", "placeholder", "test"]:
#                 logger.info(f"Skipping placeholder adjustment category name: '{adj_item.category_name}'")
#                 continue

#             adj_estimate = round(adj_item.new_estimate, 2)
#             if adj_estimate < 0:
#                 raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Estimate for category '{adj_item.category_name}' cannot be negative.")

#             if adj_item.category_name not in working_estimates: # It's a new category if not in working_estimates (which already reflects deletions)
#                 logger.info(f"Adding new category '{adj_item.category_name}' with estimate {adj_estimate}.")
#             else:
#                 logger.info(f"Updating category '{adj_item.category_name}' to estimate {adj_estimate}.")
            
#             working_estimates[adj_item.category_name] = adj_estimate
#             categories_explicitly_adjusted_or_added.add(adj_item.category_name)

#     # --- Step 4: Handle Redistribution if necessary ---
#     # This step is primarily for the "fixed total budget" scenario where new_total_budget was NOT set (or was 0)
#     # OR if new_total_budget WAS set, and we need to ensure the sum of parts matches.

#     if not working_estimates: # All categories were deleted
#         logger.info("All categories removed. Budget breakdown will be empty.")
#         plan.budget_breakdown = []
#         plan.current_total_budget = target_total_budget # This could be 0 if all deleted and no new total set
#         # total_spent will be 0, balance will be current_total_budget
#     else:
#         # Calculate sum of current working_estimates
#         current_sum_of_working_estimates = round(sum(working_estimates.values()), 2)

#         # Identify categories that were NOT explicitly adjusted/added in this request but still exist
#         untouched_remaining_categories: Dict[str, float] = {}
#         for cat_name, est_val in working_estimates.items():
#             if cat_name not in categories_explicitly_adjusted_or_added:
#                 # Get its original estimate from the plan *before any changes in this call*
#                 # This is important for proportional redistribution
#                 original_cat = next((c for c in plan.budget_breakdown if c.category_name == cat_name), None)
#                 untouched_remaining_categories[cat_name] = original_cat.estimated_amount if original_cat else 0.0


#         if budget_was_explicitly_changed_in_request or not untouched_remaining_categories:
#             # If total budget was changed by user OR if all remaining categories were explicitly set,
#             # the sum of working_estimates becomes the new current_total_budget.
#             # Any discrepancy with target_total_budget (if set) means the sum of parts dictates the total.
#             plan.current_total_budget = current_sum_of_working_estimates
#             if budget_was_explicitly_changed_in_request and abs(plan.current_total_budget - target_total_budget) > 0.01:
#                 logger.warning(f"Sum of explicit adjustments ({plan.current_total_budget}) "
#                                f"overrides requested new_total_budget ({target_total_budget}) "
#                                f"because all remaining categories were explicitly set or no untouched categories to redistribute to.")
        
#         elif untouched_remaining_categories: # There are untouched categories to redistribute to/from
#             sum_of_explicitly_set_or_added = sum(
#                 working_estimates[name] for name in categories_explicitly_adjusted_or_added if name in working_estimates
#             )
#             budget_for_untouched = round(target_total_budget - sum_of_explicitly_set_or_added, 2)
#             sum_of_original_estimates_of_untouched = sum(untouched_remaining_categories.values())

#             if budget_for_untouched < 0:
#                 logger.warning(f"Budget for untouched categories ({budget_for_untouched}) is negative. Setting them to 0.")
#                 for cat_name in untouched_remaining_categories.keys():
#                     working_estimates[cat_name] = 0.0
#             elif sum_of_original_estimates_of_untouched > 0: # Proportional redistribution
#                 for cat_name, original_est in untouched_remaining_categories.items():
#                     proportion = original_est / sum_of_original_estimates_of_untouched
#                     new_val = round(budget_for_untouched * proportion, 2)
#                     working_estimates[cat_name] = max(0.0, new_val)
#             elif budget_for_untouched > 0: # Equal distribution if original sum was 0
#                 amount_per_cat = round(budget_for_untouched / len(untouched_remaining_categories), 2)
#                 for cat_name in untouched_remaining_categories.keys():
#                     working_estimates[cat_name] = max(0.0, amount_per_cat)
            
#             # After redistribution, the sum of working_estimates should be target_total_budget
#             plan.current_total_budget = target_total_budget # Enforce the target
#             # Recalculate actual sum and adjust one category for rounding if needed
#             final_sum_after_redistribution = round(sum(working_estimates.values()), 2)
#             discrepancy = round(target_total_budget - final_sum_after_redistribution, 2)
#             if abs(discrepancy) >= 0.01 and working_estimates:
#                 # Apply to "Other" or largest category in working_estimates
#                 adj_target_name = REMAINING_BUDGET_CATEGORY_NAME if REMAINING_BUDGET_CATEGORY_NAME in working_estimates else max(working_estimates, key=working_estimates.get)
#                 if working_estimates[adj_target_name] + discrepancy >= 0:
#                     working_estimates[adj_target_name] = round(working_estimates[adj_target_name] + discrepancy, 2)
#                 else: # Cannot fully absorb
#                     logger.warning(f"Could not fully absorb rounding discrepancy of {discrepancy} into {adj_target_name}")
#                     plan.current_total_budget = round(sum(working_estimates.values()), 2) # Actual sum becomes total

#         # Reconstruct the final budget_breakdown from working_estimates
#         final_breakdown: List[BudgetCategoryBreakdown] = []
#         # Preserve order of original categories if they still exist, then add new ones
#         original_order = [cat.category_name for cat in plan.budget_breakdown]
        
#         temp_final_categories = {} # To build the list while respecting order

#         for cat_name in original_order:
#             if cat_name in working_estimates:
#                 temp_final_categories[cat_name] = working_estimates[cat_name]
        
#         for cat_name, estimate in working_estimates.items(): # Add any new categories not in original order
#             if cat_name not in temp_final_categories:
#                 temp_final_categories[cat_name] = estimate
        
#         for cat_name, estimate in temp_final_categories.items():
#              final_breakdown.append(BudgetCategoryBreakdown(category_name=cat_name, estimated_amount=estimate, percentage=0.0))
        
#         plan.budget_breakdown = final_breakdown


#     # --- Step 5: Recalculate Percentages, Spent, and Balance ---
#     if plan.current_total_budget > 0:
#         for item in plan.budget_breakdown:
#             item.percentage = round((item.estimated_amount / plan.current_total_budget) * 100, 2)
#     else:
#         for item in plan.budget_breakdown:
#             item.percentage = 0.0
#             item.estimated_amount = 0.0 # If total is 0, all estimates must be 0

#     # ** THE FIX IS HERE: Recalculate total_spent based on the new breakdown **
#     plan.total_spent = round(sum(cat.estimated_amount for cat in plan.budget_breakdown), 2)
#     plan.balance = round(plan.current_total_budget - plan.total_spent, 2)
#     plan.timestamp = datetime.now(timezone.utc)

#     # Log final state
#     logger.info(f"Final plan state for {reference_id}: Total Budget={plan.current_total_budget}, "
#                 f"Total Spent (Sum of Estimates)={plan.total_spent}, Balance={plan.balance}")
#     if abs(plan.current_total_budget - plan.total_spent) > 0.01 * max(1, len(plan.budget_breakdown)) and plan.budget_breakdown : # If balance is not near zero and there are categories
#         logger.warning(f"Plan {reference_id}: current_total_budget ({plan.current_total_budget}) "
#                        f"does not equal sum of estimates ({plan.total_spent}). Balance is {plan.balance}.")


#     document_to_db = plan.model_dump(exclude={"reference_id"})
#     try:
#         db[BUDGET_PLANS_COLLECTION].update_one({"_id": reference_id}, {"$set": document_to_db})
#         logger.info(f"Batch budget adjustments processed for _id: {reference_id}")
#     except Exception as e:
#         logger.error(f"Error saving batch adjusted budget plan for _id: {reference_id} to DB: {e}", exc_info=True)
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save batch adjusted budget plan.")

#     return plan






# # app/services/batch_adjust_service.py
# from datetime import datetime, timezone
# from typing import List, Dict
# from fastapi import HTTPException, status
# from app.models.budget import (
#     BudgetPlanDBSchema,
#     BudgetCategoryBreakdown,
#     BatchAdjustEstimatesFixedTotalRequest
# )
# from app.services.mongo_service import db
# from app.utils.logger import logger

# BUDGET_PLANS_COLLECTION = "budget_plans"
# REMAINING_BUDGET_CATEGORY_NAME = "Other Expenses / Unallocated"

# def process_batch_adjustments_fixed_total(
#     reference_id: str,
#     request_data: BatchAdjustEstimatesFixedTotalRequest
# ) -> BudgetPlanDBSchema:
#     logger.info(f"Processing batch adjustments for plan_id: {reference_id}")

#     plan_dict = db[BUDGET_PLANS_COLLECTION].find_one({"_id": reference_id})
#     if not plan_dict:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Budget plan with reference_id '{reference_id}' not found.")

#     try:
#         plan = BudgetPlanDBSchema.model_validate(plan_dict)
#     except Exception as e:
#         logger.error(f"Data validation error for existing plan {reference_id}: {e}")
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error validating existing budget plan data.")

#     # --- Determine the effective total budget for this operation ---
#     effective_total_budget: float
#     user_explicitly_set_total_budget = False
#     if request_data.new_total_budget is not None and request_data.new_total_budget > 0:
#         effective_total_budget = round(request_data.new_total_budget, 2)
#         user_explicitly_set_total_budget = True
#         logger.info(f"Request to change total budget to: {effective_total_budget}")
#     else:
#         effective_total_budget = plan.current_total_budget
#         logger.info(f"Using existing total budget: {effective_total_budget}")

#     # --- Step 1: Initialize working_estimates with current plan's categories ---
#     working_estimates: Dict[str, float] = {cat.category_name: cat.estimated_amount for cat in plan.budget_breakdown}
    
#     # --- Step 2: Process Deletions ---
#     categories_to_be_deleted_names = {
#         del_item.category_name for del_item in request_data.deletions 
#         if del_item.category_name.lower() not in ["string", "example", "placeholder", "test"]
#     }
#     for cat_name in categories_to_be_deleted_names:
#         if cat_name in working_estimates:
#             logger.info(f"Deleting category '{cat_name}' from working estimates.")
#             del working_estimates[cat_name]
#         else:
#             logger.warning(f"Category '{cat_name}' requested for deletion not found in current plan estimates.")

#     # --- Step 3: Process Adjustments (Updates and Additions) ---
#     categories_explicitly_adjusted_or_added = set()
#     sum_of_explicitly_set_estimates_in_request = 0.0 # Sum of valid adjustments from request

#     if request_data.adjustments:
#         for adj_item in request_data.adjustments:
#             if adj_item.category_name.lower() in ["string", "example", "placeholder", "test"]:
#                 logger.info(f"Skipping placeholder adjustment category name: '{adj_item.category_name}'")
#                 continue
#             if adj_item.new_estimate < 0: # Allow 0, but not negative
#                 raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Estimate for category '{adj_item.category_name}' cannot be negative.")
            
#             adj_estimate = round(adj_item.new_estimate, 2)
            
#             if adj_item.category_name not in working_estimates and adj_item.category_name not in categories_to_be_deleted_names:
#                 logger.info(f"New category '{adj_item.category_name}' specified in adjustments with estimate {adj_estimate}.")
#             elif adj_item.category_name in working_estimates: # It's an update to an existing, non-deleted category
#                 logger.info(f"Updating category '{adj_item.category_name}' to estimate {adj_estimate}.")
            
#             if adj_item.category_name not in categories_to_be_deleted_names: # Only process if not marked for deletion
#                 working_estimates[adj_item.category_name] = adj_estimate
#                 categories_explicitly_adjusted_or_added.add(adj_item.category_name)
#                 sum_of_explicitly_set_estimates_in_request += adj_estimate


#     # --- Step 4: Handle Redistribution and Finalize current_total_budget ---
#     if not working_estimates: # All categories were deleted or none existed to begin with
#         logger.info("All categories removed or no categories to process. Budget breakdown will be empty.")
#         plan.budget_breakdown = []
#         plan.current_total_budget = effective_total_budget # The user-set total, or original if not set
#     else:
#         # Identify categories that were NOT explicitly adjusted/added in this request but still exist in working_estimates
#         untouched_remaining_categories: Dict[str, float] = {} # name: its estimate in working_estimates *before* redistribution
#         for cat_name, est_val in working_estimates.items():
#             if cat_name not in categories_explicitly_adjusted_or_added:
#                 untouched_remaining_categories[cat_name] = est_val

#         if not untouched_remaining_categories and categories_explicitly_adjusted_or_added:
#             # All remaining categories were explicitly set by the user in this request.
#             # Their sum becomes the new current_total_budget, overriding effective_total_budget if different.
#             new_total_from_parts = round(sum(working_estimates.values()), 2)
#             if abs(new_total_from_parts - effective_total_budget) > 0.01 and user_explicitly_set_total_budget:
#                 logger.warning(f"Sum of all explicitly set categories ({new_total_from_parts}) "
#                                f"differs from the requested new_total_budget ({effective_total_budget}). "
#                                f"The sum of parts will define the new total budget.")
#             effective_total_budget = new_total_from_parts
#             logger.info(f"All remaining categories were explicitly set. New total budget is: {effective_total_budget}")
        
#         elif untouched_remaining_categories:
#             # There are untouched categories. Redistribute budget among them to meet effective_total_budget.
#             current_sum_of_explicitly_adjusted = sum(
#                 working_estimates[name] for name in categories_explicitly_adjusted_or_added
#             )
#             budget_for_untouched = round(effective_total_budget - current_sum_of_explicitly_adjusted, 2)
#             sum_of_original_estimates_of_untouched = sum(untouched_remaining_categories.values())

#             if budget_for_untouched < 0:
#                 logger.warning(f"Budget for untouched categories ({budget_for_untouched}) is negative. Setting them to 0.")
#                 for cat_name in untouched_remaining_categories.keys():
#                     working_estimates[cat_name] = 0.0
#             elif sum_of_original_estimates_of_untouched > 0: # Proportional redistribution
#                 for cat_name, original_est_in_working_estimates in untouched_remaining_categories.items():
#                     proportion = original_est_in_working_estimates / sum_of_original_estimates_of_untouched
#                     new_val = round(budget_for_untouched * proportion, 2)
#                     working_estimates[cat_name] = max(0.0, new_val)
#             elif budget_for_untouched > 0: # Equal distribution if original sum was 0
#                 amount_per_cat = round(budget_for_untouched / len(untouched_remaining_categories), 2)
#                 for cat_name in untouched_remaining_categories.keys():
#                     working_estimates[cat_name] = max(0.0, amount_per_cat)
        
#         # Final pass to ensure sum of working_estimates matches effective_total_budget due to rounding
#         current_sum_final = round(sum(working_estimates.values()), 2)
#         discrepancy = round(effective_total_budget - current_sum_final, 2)
#         if abs(discrepancy) >= 0.01 and working_estimates:
#             logger.info(f"Final rounding discrepancy of {discrepancy} to match effective total. Adjusting.")
#             # Apply to "Other" or largest category in working_estimates
#             adj_target_name = REMAINING_BUDGET_CATEGORY_NAME if REMAINING_BUDGET_CATEGORY_NAME in working_estimates else max(working_estimates, key=working_estimates.get, default=None)
#             if adj_target_name and (working_estimates[adj_target_name] + discrepancy >= 0):
#                 working_estimates[adj_target_name] = round(working_estimates[adj_target_name] + discrepancy, 2)
#             else:
#                 logger.warning(f"Could not fully absorb rounding discrepancy of {discrepancy}.")
#                 effective_total_budget = round(sum(working_estimates.values()), 2) # Actual sum becomes total

#         plan.current_total_budget = effective_total_budget
        
#         # Reconstruct the final budget_breakdown from working_estimates
#         final_breakdown: List[BudgetCategoryBreakdown] = []
#         original_order = [cat.category_name for cat in plan.budget_breakdown] # Original order from DB
        
#         present_categories_in_order = [name for name in original_order if name in working_estimates]
#         newly_added_categories = [name for name in working_estimates if name not in present_categories_in_order]
        
#         for cat_name in present_categories_in_order + newly_added_categories:
#             final_breakdown.append(BudgetCategoryBreakdown(category_name=cat_name, estimated_amount=working_estimates[cat_name], percentage=0.0))
#         plan.budget_breakdown = final_breakdown

#     # --- Step 5: Recalculate Percentages, Spent, and Balance ---
#     if plan.current_total_budget > 0:
#         for item in plan.budget_breakdown:
#             item.percentage = round((item.estimated_amount / plan.current_total_budget) * 100, 2)
#     else:
#         for item in plan.budget_breakdown:
#             item.percentage = 0.0
#             item.estimated_amount = 0.0

#     plan.total_spent = round(sum(cat.estimated_amount for cat in plan.budget_breakdown), 2)
#     plan.balance = round(plan.current_total_budget - plan.total_spent, 2)
#     plan.timestamp = datetime.now(timezone.utc)

#     logger.info(f"Final plan state for {reference_id}: Total Budget={plan.current_total_budget}, "
#                 f"Sum of Estimates (Spent)={plan.total_spent}, Balance={plan.balance}")

#     document_to_db = plan.model_dump(exclude={"reference_id"})
#     try:
#         db[BUDGET_PLANS_COLLECTION].update_one({"_id": reference_id}, {"$set": document_to_db})
#         logger.info(f"Batch budget adjustments processed for _id: {reference_id}")
#     except Exception as e:
#         logger.error(f"Error saving batch adjusted budget plan for _id: {reference_id} to DB: {e}", exc_info=True)
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save batch adjusted budget plan.")

#     return plan


# # app/services/batch_adjust_service.py
# from datetime import datetime, timezone
# from typing import List, Dict
# from fastapi import HTTPException, status
# from app.models.budget import (
#     BudgetPlanDBSchema,
#     BudgetCategoryBreakdown,
#     BatchAdjustEstimatesFixedTotalRequest
# )
# from app.services.mongo_service import db
# from app.utils.logger import logger

# BUDGET_PLANS_COLLECTION = "budget_plans"
# REMAINING_BUDGET_CATEGORY_NAME = "Other Expenses / Unallocated"

# def process_batch_adjustments_fixed_total(
#     reference_id: str,
#     request_data: BatchAdjustEstimatesFixedTotalRequest
# ) -> BudgetPlanDBSchema:
#     logger.info(f"Processing batch adjustments for plan_id: {reference_id}")

#     plan_dict = db[BUDGET_PLANS_COLLECTION].find_one({"_id": reference_id})
#     if not plan_dict:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Budget plan with reference_id '{reference_id}' not found.")

#     try:
#         plan = BudgetPlanDBSchema.model_validate(plan_dict)
#     except Exception as e:
#         logger.error(f"Data validation error for existing plan {reference_id}: {e}")
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error validating existing budget plan data.")

#     # --- Determine the effective total budget for this operation ---
#     effective_total_budget: float
#     user_explicitly_set_total_budget = False
#     if request_data.new_total_budget is not None and request_data.new_total_budget > 0:
#         effective_total_budget = round(request_data.new_total_budget, 2)
#         user_explicitly_set_total_budget = True
#         logger.info(f"Request to change total budget to: {effective_total_budget}")
#     else:
#         effective_total_budget = plan.current_total_budget
#         logger.info(f"Using existing total budget: {effective_total_budget}")

#     # --- Step 1: Initialize working_estimates with current plan's categories ---
#     working_estimates: Dict[str, float] = {cat.category_name: cat.estimated_amount for cat in plan.budget_breakdown}
    
#     # --- Step 2: Process Deletions ---
#     categories_to_be_deleted_names = {
#         del_item.category_name for del_item in request_data.deletions 
#         if del_item.category_name.lower() not in ["string", "example", "placeholder", "test"]
#     }
#     for cat_name in categories_to_be_deleted_names:
#         if cat_name in working_estimates:
#             logger.info(f"Deleting category '{cat_name}' from working estimates.")
#             del working_estimates[cat_name]
#         else:
#             logger.warning(f"Category '{cat_name}' requested for deletion not found in current plan estimates.")

#     # --- Step 3: Process Adjustments (Updates and Additions) ---
#     categories_explicitly_adjusted_or_added = set()
#     sum_of_explicitly_set_estimates_in_request = 0.0 # Sum of valid adjustments from request

#     if request_data.adjustments:
#         for adj_item in request_data.adjustments:
#             if adj_item.category_name.lower() in ["string", "example", "placeholder", "test"]:
#                 logger.info(f"Skipping placeholder adjustment category name: '{adj_item.category_name}'")
#                 continue
#             if adj_item.new_estimate < 0: # Allow 0, but not negative
#                 raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Estimate for category '{adj_item.category_name}' cannot be negative.")
            
#             adj_estimate = round(adj_item.new_estimate, 2)
            
#             if adj_item.category_name not in working_estimates and adj_item.category_name not in categories_to_be_deleted_names:
#                 logger.info(f"New category '{adj_item.category_name}' specified in adjustments with estimate {adj_estimate}.")
#             elif adj_item.category_name in working_estimates: # It's an update to an existing, non-deleted category
#                 logger.info(f"Updating category '{adj_item.category_name}' to estimate {adj_estimate}.")
            
#             if adj_item.category_name not in categories_to_be_deleted_names: # Only process if not marked for deletion
#                 working_estimates[adj_item.category_name] = adj_estimate
#                 categories_explicitly_adjusted_or_added.add(adj_item.category_name)
#                 sum_of_explicitly_set_estimates_in_request += adj_estimate

#     # --- Step 4: Handle Redistribution and Finalize current_total_budget ---
#     if not working_estimates: # All categories were deleted or none existed to begin with
#         logger.info("All categories removed or no categories to process. Budget breakdown will be empty.")
#         plan.budget_breakdown = []
#         plan.current_total_budget = effective_total_budget # The user-set total, or original if not set
#     else:
#         # Identify categories that were NOT explicitly adjusted/added in this request but still exist in working_estimates
#         untouched_remaining_categories: Dict[str, float] = {} # name: its estimate in working_estimates *before* redistribution
#         for cat_name, est_val in working_estimates.items():
#             if cat_name not in categories_explicitly_adjusted_or_added:
#                 untouched_remaining_categories[cat_name] = est_val

#         # FIXED LOGIC: Always respect user's explicit total budget when provided
#         if user_explicitly_set_total_budget:
#             # User explicitly set a new total budget - always use it
#             plan.current_total_budget = effective_total_budget
#             logger.info(f"Using user-specified total budget: {effective_total_budget}")
            
#             if not untouched_remaining_categories:
#                 # All remaining categories were explicitly set by user
#                 # Check if sum exceeds the total budget and log warning if needed
#                 sum_of_all_estimates = round(sum(working_estimates.values()), 2)
#                 if sum_of_all_estimates > effective_total_budget:
#                     logger.warning(f"Sum of all category estimates ({sum_of_all_estimates}) "
#                                    f"exceeds the specified total budget ({effective_total_budget}). "
#                                    f"This will result in a negative balance.")
#                 elif sum_of_all_estimates < effective_total_budget:
#                     logger.info(f"Sum of all category estimates ({sum_of_all_estimates}) "
#                                 f"is less than the specified total budget ({effective_total_budget}). "
#                                 f"This will result in a positive balance.")
#             else:
#                 # There are untouched categories to redistribute
#                 current_sum_of_explicitly_adjusted = sum(
#                     working_estimates[name] for name in categories_explicitly_adjusted_or_added
#                 )
#                 budget_for_untouched = round(effective_total_budget - current_sum_of_explicitly_adjusted, 2)
#                 sum_of_original_estimates_of_untouched = sum(untouched_remaining_categories.values())

#                 if budget_for_untouched < 0:
#                     logger.warning(f"Budget for untouched categories ({budget_for_untouched}) is negative. Setting them to 0.")
#                     for cat_name in untouched_remaining_categories.keys():
#                         working_estimates[cat_name] = 0.0
#                 elif sum_of_original_estimates_of_untouched > 0: # Proportional redistribution
#                     for cat_name, original_est_in_working_estimates in untouched_remaining_categories.items():
#                         proportion = original_est_in_working_estimates / sum_of_original_estimates_of_untouched
#                         new_val = round(budget_for_untouched * proportion, 2)
#                         working_estimates[cat_name] = max(0.0, new_val)
#                 elif budget_for_untouched > 0: # Equal distribution if original sum was 0
#                     amount_per_cat = round(budget_for_untouched / len(untouched_remaining_categories), 2)
#                     for cat_name in untouched_remaining_categories.keys():
#                         working_estimates[cat_name] = max(0.0, amount_per_cat)
        
#         else:
#             # User did NOT explicitly set a total budget
#             if not untouched_remaining_categories and categories_explicitly_adjusted_or_added:
#                 # All remaining categories were explicitly set by the user.
#                 # Their sum becomes the new current_total_budget.
#                 new_total_from_parts = round(sum(working_estimates.values()), 2)
#                 effective_total_budget = new_total_from_parts
#                 plan.current_total_budget = effective_total_budget
#                 logger.info(f"All remaining categories were explicitly set. New total budget is: {effective_total_budget}")
#             elif untouched_remaining_categories:
#                 # There are untouched categories. Keep the existing total budget and redistribute.
#                 plan.current_total_budget = effective_total_budget
#                 current_sum_of_explicitly_adjusted = sum(
#                     working_estimates[name] for name in categories_explicitly_adjusted_or_added
#                 )
#                 budget_for_untouched = round(effective_total_budget - current_sum_of_explicitly_adjusted, 2)
#                 sum_of_original_estimates_of_untouched = sum(untouched_remaining_categories.values())

#                 if budget_for_untouched < 0:
#                     logger.warning(f"Budget for untouched categories ({budget_for_untouched}) is negative. Setting them to 0.")
#                     for cat_name in untouched_remaining_categories.keys():
#                         working_estimates[cat_name] = 0.0
#                 elif sum_of_original_estimates_of_untouched > 0: # Proportional redistribution
#                     for cat_name, original_est_in_working_estimates in untouched_remaining_categories.items():
#                         proportion = original_est_in_working_estimates / sum_of_original_estimates_of_untouched
#                         new_val = round(budget_for_untouched * proportion, 2)
#                         working_estimates[cat_name] = max(0.0, new_val)
#                 elif budget_for_untouched > 0: # Equal distribution if original sum was 0
#                     amount_per_cat = round(budget_for_untouched / len(untouched_remaining_categories), 2)
#                     for cat_name in untouched_remaining_categories.keys():
#                         working_estimates[cat_name] = max(0.0, amount_per_cat)
        
#         # Final pass to handle any rounding discrepancies when user explicitly set total budget
#         if user_explicitly_set_total_budget and untouched_remaining_categories:
#             current_sum_final = round(sum(working_estimates.values()), 2)
#             discrepancy = round(effective_total_budget - current_sum_final, 2)
#             if abs(discrepancy) >= 0.01 and working_estimates:
#                 logger.info(f"Final rounding discrepancy of {discrepancy} to match effective total. Adjusting.")
#                 # Apply to "Other" or largest untouched category in working_estimates
#                 adj_target_name = None
#                 if REMAINING_BUDGET_CATEGORY_NAME in untouched_remaining_categories:
#                     adj_target_name = REMAINING_BUDGET_CATEGORY_NAME
#                 elif untouched_remaining_categories:
#                     adj_target_name = max(untouched_remaining_categories, key=untouched_remaining_categories.get)
                
#                 if adj_target_name and (working_estimates[adj_target_name] + discrepancy >= 0):
#                     working_estimates[adj_target_name] = round(working_estimates[adj_target_name] + discrepancy, 2)
#                 else:
#                     logger.warning(f"Could not fully absorb rounding discrepancy of {discrepancy}.")
        
#         # Reconstruct the final budget_breakdown from working_estimates
#         final_breakdown: List[BudgetCategoryBreakdown] = []
#         original_order = [cat.category_name for cat in plan.budget_breakdown] # Original order from DB
        
#         present_categories_in_order = [name for name in original_order if name in working_estimates]
#         newly_added_categories = [name for name in working_estimates if name not in present_categories_in_order]
        
#         for cat_name in present_categories_in_order + newly_added_categories:
#             final_breakdown.append(BudgetCategoryBreakdown(category_name=cat_name, estimated_amount=working_estimates[cat_name], percentage=0.0))
#         plan.budget_breakdown = final_breakdown

#     # --- Step 5: Recalculate Percentages, Spent, and Balance ---
#     if plan.current_total_budget > 0:
#         for item in plan.budget_breakdown:
#             item.percentage = round((item.estimated_amount / plan.current_total_budget) * 100, 2)
#     else:
#         for item in plan.budget_breakdown:
#             item.percentage = 0.0
#             item.estimated_amount = 0.0

#     plan.total_spent = round(sum(cat.estimated_amount for cat in plan.budget_breakdown), 2)
#     plan.balance = round(plan.current_total_budget - plan.total_spent, 2)
#     plan.timestamp = datetime.now(timezone.utc)

#     logger.info(f"Final plan state for {reference_id}: Total Budget={plan.current_total_budget}, "
#                 f"Sum of Estimates (Spent)={plan.total_spent}, Balance={plan.balance}")

#     document_to_db = plan.model_dump(exclude={"reference_id"})
#     try:
#         db[BUDGET_PLANS_COLLECTION].update_one({"_id": reference_id}, {"$set": document_to_db})
#         logger.info(f"Batch budget adjustments processed for _id: {reference_id}")
#     except Exception as e:
#         logger.error(f"Error saving batch adjusted budget plan for _id: {reference_id} to DB: {e}", exc_info=True)
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save batch adjusted budget plan.")

#     return plan


# app/services/batch_adjust_service.py
from datetime import datetime, timezone
from typing import List, Dict
from fastapi import HTTPException, status
from app.models.budget import (
    BudgetPlanDBSchema,
    BudgetCategoryBreakdown,
    BatchAdjustEstimatesFixedTotalRequest
)
from app.services.mongo_service import db
from app.utils.logger import logger

BUDGET_PLANS_COLLECTION = "budget_plans"
REMAINING_BUDGET_CATEGORY_NAME = "Other Expenses / Unallocated"

def process_batch_adjustments_fixed_total(
    reference_id: str,
    request_data: BatchAdjustEstimatesFixedTotalRequest
) -> BudgetPlanDBSchema:
    logger.info(f"Processing batch adjustments for plan_id: {reference_id}")

    plan_dict = db[BUDGET_PLANS_COLLECTION].find_one({"reference_id": reference_id})
    if not plan_dict:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Budget plan with reference_id '{reference_id}' not found.")

    try:
        plan = BudgetPlanDBSchema.model_validate(plan_dict)
    except Exception as e:
        logger.error(f"Data validation error for existing plan {reference_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error validating existing budget plan data.")

    # --- Determine the effective total budget for this operation ---
    effective_total_budget: float
    user_explicitly_set_total_budget = False
    if request_data.new_total_budget is not None and request_data.new_total_budget > 0:
        effective_total_budget = round(request_data.new_total_budget, 2)
        user_explicitly_set_total_budget = True
        logger.info(f"Request to change total budget to: {effective_total_budget}")
    else:
        effective_total_budget = plan.current_total_budget
        logger.info(f"Using existing total budget: {effective_total_budget}")

    # --- Step 1: Initialize working_estimates with current plan's categories ---
    working_estimates: Dict[str, float] = {cat.category_name: cat.estimated_amount for cat in plan.budget_breakdown}
    
    # --- Step 2: Process Deletions ---
    categories_to_be_deleted_names = {
        del_item.category_name for del_item in request_data.deletions 
        if del_item.category_name.lower() not in ["string", "example", "placeholder", "test"]
    }
    for cat_name in categories_to_be_deleted_names:
        if cat_name in working_estimates:
            logger.info(f"Deleting category '{cat_name}' from working estimates.")
            del working_estimates[cat_name]
        else:
            logger.warning(f"Category '{cat_name}' requested for deletion not found in current plan estimates.")

    # --- Step 3: Process Adjustments (Updates and Additions) ---
    categories_explicitly_adjusted_or_added = set()
    sum_of_explicitly_set_estimates_in_request = 0.0 # Sum of valid adjustments from request

    if request_data.adjustments:
        for adj_item in request_data.adjustments:
            if adj_item.category_name.lower() in ["string", "example", "placeholder", "test"]:
                logger.info(f"Skipping placeholder adjustment category name: '{adj_item.category_name}'")
                continue
            if adj_item.new_estimate < 0: # Allow 0, but not negative
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Estimate for category '{adj_item.category_name}' cannot be negative.")
            
            adj_estimate = round(adj_item.new_estimate, 2)
            
            if adj_item.category_name not in working_estimates and adj_item.category_name not in categories_to_be_deleted_names:
                logger.info(f"New category '{adj_item.category_name}' specified in adjustments with estimate {adj_estimate}.")
            elif adj_item.category_name in working_estimates: # It's an update to an existing, non-deleted category
                logger.info(f"Updating category '{adj_item.category_name}' to estimate {adj_estimate}.")
            
            if adj_item.category_name not in categories_to_be_deleted_names: # Only process if not marked for deletion
                working_estimates[adj_item.category_name] = adj_estimate
                categories_explicitly_adjusted_or_added.add(adj_item.category_name)
                sum_of_explicitly_set_estimates_in_request += adj_estimate

    # --- Step 4: Handle Redistribution and Finalize current_total_budget ---
    if not working_estimates: # All categories were deleted or none existed to begin with
        logger.info("All categories removed or no categories to process. Budget breakdown will be empty.")
        plan.budget_breakdown = []
        plan.current_total_budget = effective_total_budget # The user-set total, or original if not set
    else:
        # Identify categories that were NOT explicitly adjusted/added in this request but still exist in working_estimates
        untouched_remaining_categories: Dict[str, float] = {} # name: its estimate in working_estimates *before* redistribution
        for cat_name, est_val in working_estimates.items():
            if cat_name not in categories_explicitly_adjusted_or_added:
                untouched_remaining_categories[cat_name] = est_val

        # FIXED LOGIC: Always respect user's explicit total budget when provided
        if user_explicitly_set_total_budget:
            # User explicitly set a new total budget - always use it
            plan.current_total_budget = effective_total_budget
            logger.info(f"Using user-specified total budget: {effective_total_budget}")
            
            if not untouched_remaining_categories:
                # All remaining categories were explicitly set by user
                # Check if sum exceeds the total budget and log warning if needed
                sum_of_all_estimates = round(sum(working_estimates.values()), 2)
                if sum_of_all_estimates > effective_total_budget:
                    logger.warning(f"Sum of all category estimates ({sum_of_all_estimates}) "
                                   f"exceeds the specified total budget ({effective_total_budget}). "
                                   f"This will result in a negative balance.")
                elif sum_of_all_estimates < effective_total_budget:
                    logger.info(f"Sum of all category estimates ({sum_of_all_estimates}) "
                                f"is less than the specified total budget ({effective_total_budget}). "
                                f"This will result in a positive balance.")
            else:
                # There are untouched categories to redistribute
                current_sum_of_explicitly_adjusted = sum(
                    working_estimates[name] for name in categories_explicitly_adjusted_or_added
                )
                budget_for_untouched = round(effective_total_budget - current_sum_of_explicitly_adjusted, 2)
                sum_of_original_estimates_of_untouched = sum(untouched_remaining_categories.values())

                if budget_for_untouched < 0:
                    logger.warning(f"Budget for untouched categories ({budget_for_untouched}) is negative. Setting them to 0.")
                    for cat_name in untouched_remaining_categories.keys():
                        working_estimates[cat_name] = 0.0
                elif sum_of_original_estimates_of_untouched > 0: # Proportional redistribution
                    for cat_name, original_est_in_working_estimates in untouched_remaining_categories.items():
                        proportion = original_est_in_working_estimates / sum_of_original_estimates_of_untouched
                        new_val = round(budget_for_untouched * proportion, 2)
                        working_estimates[cat_name] = max(0.0, new_val)
                elif budget_for_untouched > 0: # Equal distribution if original sum was 0
                    amount_per_cat = round(budget_for_untouched / len(untouched_remaining_categories), 2)
                    for cat_name in untouched_remaining_categories.keys():
                        working_estimates[cat_name] = max(0.0, amount_per_cat)
        
        else:
            # User did NOT explicitly set a total budget - ALWAYS keep the original budget
            plan.current_total_budget = effective_total_budget  # This is the original budget
            logger.info(f"No new total budget specified. Keeping original budget: {effective_total_budget}")
            
            
            if untouched_remaining_categories:
                # There are untouched categories. Keep the existing total budget and redistribute.
                current_sum_of_explicitly_adjusted = sum(
                    working_estimates[name] for name in categories_explicitly_adjusted_or_added
                )
                budget_for_untouched = round(effective_total_budget - current_sum_of_explicitly_adjusted, 2)
                sum_of_original_estimates_of_untouched = sum(untouched_remaining_categories.values())

                if budget_for_untouched < 0:
                    logger.warning(f"Budget for untouched categories ({budget_for_untouched}) is negative. Setting them to 0.")
                    for cat_name in untouched_remaining_categories.keys():
                        working_estimates[cat_name] = 0.0
                elif sum_of_original_estimates_of_untouched > 0: # Proportional redistribution
                    for cat_name, original_est_in_working_estimates in untouched_remaining_categories.items():
                        proportion = original_est_in_working_estimates / sum_of_original_estimates_of_untouched
                        new_val = round(budget_for_untouched * proportion, 2)
                        working_estimates[cat_name] = max(0.0, new_val)
                elif budget_for_untouched > 0: # Equal distribution if original sum was 0
                    amount_per_cat = round(budget_for_untouched / len(untouched_remaining_categories), 2)
                    for cat_name in untouched_remaining_categories.keys():
                        working_estimates[cat_name] = max(0.0, amount_per_cat)
            # If all categories were explicitly adjusted and no untouched categories remain,
            # we keep the original total budget and allow for positive/negative balance
        
        # Final pass to handle any rounding discrepancies when user explicitly set total budget
        if user_explicitly_set_total_budget and untouched_remaining_categories:
            current_sum_final = round(sum(working_estimates.values()), 2)
            discrepancy = round(effective_total_budget - current_sum_final, 2)
            if abs(discrepancy) >= 0.01 and working_estimates:
                logger.info(f"Final rounding discrepancy of {discrepancy} to match effective total. Adjusting.")
                # Apply to "Other" or largest untouched category in working_estimates
                adj_target_name = None
                if REMAINING_BUDGET_CATEGORY_NAME in untouched_remaining_categories:
                    adj_target_name = REMAINING_BUDGET_CATEGORY_NAME
                elif untouched_remaining_categories:
                    adj_target_name = max(untouched_remaining_categories, key=untouched_remaining_categories.get)
                
                if adj_target_name and (working_estimates[adj_target_name] + discrepancy >= 0):
                    working_estimates[adj_target_name] = round(working_estimates[adj_target_name] + discrepancy, 2)
                else:
                    logger.warning(f"Could not fully absorb rounding discrepancy of {discrepancy}.")
        
        # Reconstruct the final budget_breakdown from working_estimates
        final_breakdown: List[BudgetCategoryBreakdown] = []
        original_order = [cat.category_name for cat in plan.budget_breakdown] # Original order from DB
        
        present_categories_in_order = [name for name in original_order if name in working_estimates]
        newly_added_categories = [name for name in working_estimates if name not in present_categories_in_order]
        
        for cat_name in present_categories_in_order + newly_added_categories:
            final_breakdown.append(BudgetCategoryBreakdown(category_name=cat_name, estimated_amount=working_estimates[cat_name], percentage=0.0))
        plan.budget_breakdown = final_breakdown

    # --- Step 5: Recalculate Percentages, Spent, and Balance ---
    if plan.current_total_budget > 0:
        for item in plan.budget_breakdown:
            item.percentage = round((item.estimated_amount / plan.current_total_budget) * 100, 2)
    else:
        for item in plan.budget_breakdown:
            item.percentage = 0.0
            item.estimated_amount = 0.0

    plan.total_spent = round(sum(cat.estimated_amount for cat in plan.budget_breakdown), 2)
    plan.balance = round(plan.current_total_budget - plan.total_spent, 2)
    plan.timestamp = datetime.now(timezone.utc)

    logger.info(f"Final plan state for {reference_id}: Total Budget={plan.current_total_budget}, "
                f"Sum of Estimates (Spent)={plan.total_spent}, Balance={plan.balance}")

    document_to_db = plan.model_dump()
    try:
        db[BUDGET_PLANS_COLLECTION].update_one({"reference_id": reference_id}, {"$set": document_to_db})
        logger.info(f"Batch budget adjustments processed for _id: {reference_id}")
    except Exception as e:
        logger.error(f"Error saving batch adjusted budget plan for _id: {reference_id} to DB: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save batch adjusted budget plan.")

    return plan