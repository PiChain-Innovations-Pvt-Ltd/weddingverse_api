# # # # app/services/batch_adjust_service.py
# # # from datetime import datetime, timezone
# # # from typing import List, Dict
# # # from fastapi import HTTPException, status
# # # from app.models.budget import (
# # #     BudgetPlanDBSchema,
# # #     BudgetCategoryBreakdown,
# # #     BatchAdjustEstimatesFixedTotalRequest
# # # )
# # # from app.services.mongo_service import db
# # # from app.utils.logger import logger

# # # BUDGET_PLANS_COLLECTION = "budget_plans"
# # # REMAINING_BUDGET_CATEGORY_NAME = "Other Expenses / Unallocated"

# # # def process_batch_adjustments_fixed_total(
# # #     reference_id: str,
# # #     request_data: BatchAdjustEstimatesFixedTotalRequest
# # # ) -> BudgetPlanDBSchema:
# # #     """
# # #     Process batch adjustments including updates, additions, and deletions.
    
# # #     Deletion Behavior:
# # #     1. Single category deleted: Amount redistributed to remaining categories, total budget unchanged
# # #     2. Multiple categories deleted: Combined amounts redistributed to remaining categories
# # #     3. ALL categories deleted: 
# # #        - Budget breakdown becomes empty []
# # #        - Total budget maintained (original or user-specified)
# # #        - Total spent becomes 0 (no categories = no spending)
# # #        - Balance becomes equal to total budget (everything available)
# # #        - Any actual costs from deleted categories are effectively "refunded"
    
# # #     Example - All categories deleted:
# # #     Before: Total=30000, Venue=15000(paid 12000), Caterer=10000(paid 5000), DJ=5000(unpaid)
# # #     After:  Total=30000, Categories=[], Spent=0, Balance=30000
# # #     Result: User gets full budget back as available balance
# # #     """
# # #     logger.info(f"Processing batch adjustments for plan_id: {reference_id}")

# # #     # Fetch the existing budget plan using 'reference_id'
# # #     plan_dict = db[BUDGET_PLANS_COLLECTION].find_one({"reference_id": reference_id})
# # #     if not plan_dict:
# # #         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Budget plan with reference_id '{reference_id}' not found.")

# # #     try:
# # #         # Validate and load the existing plan
# # #         plan = BudgetPlanDBSchema.model_validate(plan_dict)
# # #     except Exception as e:
# # #         logger.error(f"Data validation error for existing plan {reference_id}: {e}")
# # #         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error validating existing budget plan data.")

# # #     # --- Determine the effective total budget for this operation ---
# # #     effective_total_budget: float
# # #     user_explicitly_set_total_budget = False
# # #     if request_data.new_total_budget is not None and request_data.new_total_budget > 0:
# # #         effective_total_budget = round(request_data.new_total_budget, 2)
# # #         user_explicitly_set_total_budget = True
# # #         logger.info(f"Request to change total budget to: {effective_total_budget}")
# # #     else:
# # #         # Keep the original total budget - this is key for proper redistribution
# # #         effective_total_budget = plan.current_total_budget
# # #         logger.info(f"Using existing total budget: {effective_total_budget}")

# # #     # --- Step 1: Initialize working_categories_map with current plan's categories ---
# # #     working_categories_map: Dict[str, BudgetCategoryBreakdown] = {
# # #         cat.category_name: cat.model_copy() for cat in plan.budget_breakdown
# # #     }
    
# # #     # --- Step 2: Process Deletions and handle actual costs ---
# # #     categories_to_be_deleted_names = {
# # #         del_item.category_name for del_item in request_data.deletions 
# # #         if del_item.category_name.lower() not in ["string", "example", "placeholder", "test"] # Skip placeholders
# # #     }
    
# # #     # Track deleted amounts and actual costs for redistribution
# # #     deleted_estimated_amount = 0.0
# # #     deleted_actual_cost = 0.0
    
# # #     for cat_name in categories_to_be_deleted_names:
# # #         if cat_name in working_categories_map:
# # #             deleted_category = working_categories_map[cat_name]
# # #             deleted_estimated_amount += deleted_category.estimated_amount
            
# # #             # Handle actual cost of deleted category
# # #             if deleted_category.actual_cost is not None and deleted_category.actual_cost > 0:
# # #                 deleted_actual_cost += deleted_category.actual_cost
# # #                 logger.info(f"Deleted category '{cat_name}' had actual cost of {deleted_category.actual_cost}")
            
# # #             logger.info(f"Deleting category '{cat_name}' with estimated amount {deleted_category.estimated_amount}")
# # #             del working_categories_map[cat_name]
# # #         else:
# # #             logger.warning(f"Category '{cat_name}' requested for deletion not found in current plan estimates.")

# # #     # --- Step 3: Process Adjustments (Updates and Additions) ---
# # #     categories_explicitly_adjusted_or_added = set()
    
# # #     if request_data.adjustments:
# # #         for adj_item in request_data.adjustments:
# # #             if adj_item.category_name.lower() in ["string", "example", "placeholder", "test"]:
# # #                 logger.info(f"Skipping placeholder adjustment category name: '{adj_item.category_name}'")
# # #                 continue
            
# # #             # Get actual_cost and payment_status with proper attribute access
# # #             actual_cost = getattr(adj_item, 'actual_cost', None)
# # #             payment_status = getattr(adj_item, 'payment_status', None)
            
# # #             # Determine if this is just an actual_cost/payment_status update
# # #             # If new_estimate is 0 AND we have actual_cost or payment_status, treat as cost-only update
# # #             is_cost_only_update = (
# # #                 adj_item.new_estimate == 0 and 
# # #                 (actual_cost is not None or payment_status is not None)
# # #             )
            
# # #             # Skip if no meaningful change (truly empty adjustment)
# # #             if adj_item.new_estimate == 0 and actual_cost is None and payment_status is None:
# # #                 logger.info(f"Skipping adjustment for '{adj_item.category_name}' as no meaningful change.")
# # #                 continue

# # #             # Estimates cannot be negative
# # #             if adj_item.new_estimate < 0:
# # #                 raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Estimate for category '{adj_item.category_name}' cannot be negative.")
            
# # #             # Actual cost cannot be negative if provided
# # #             if actual_cost is not None and actual_cost < 0:
# # #                  raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Actual cost for category '{adj_item.category_name}' cannot be negative.")

# # #             adj_new_estimate = round(adj_item.new_estimate, 2) if not is_cost_only_update else None
# # #             adj_actual_cost = round(actual_cost, 2) if actual_cost is not None else None

# # #             if adj_item.category_name not in categories_to_be_deleted_names:
# # #                 if adj_item.category_name in working_categories_map: # Update existing category
# # #                     cat_obj = working_categories_map[adj_item.category_name]
                    
# # #                     if is_cost_only_update:
# # #                         # Only update actual_cost and payment_status, keep existing estimate
# # #                         logger.info(f"Updating only actual_cost/payment_status for '{adj_item.category_name}'. "
# # #                                    f"Estimate remains: {cat_obj.estimated_amount}")
# # #                         # Don't add to explicitly adjusted categories since estimate wasn't changed
# # #                     else:
# # #                         # Update the estimate
# # #                         logger.info(f"Updating category '{adj_item.category_name}' estimate from {cat_obj.estimated_amount} to {adj_new_estimate}.")
# # #                         cat_obj.estimated_amount = adj_new_estimate
# # #                         categories_explicitly_adjusted_or_added.add(adj_item.category_name)
                    
# # #                     # Always update actual_cost and payment_status if provided
# # #                     if hasattr(cat_obj, 'actual_cost'):
# # #                         cat_obj.actual_cost = adj_actual_cost
# # #                     if hasattr(cat_obj, 'payment_status'):
# # #                         cat_obj.payment_status = payment_status
                        
# # #                 else: # Add new category
# # #                     if is_cost_only_update:
# # #                         # For new categories, if it's cost-only update, set estimate to 0
# # #                         estimate_for_new = 0.0
# # #                         logger.info(f"Adding new category '{adj_item.category_name}' with cost-only update. Estimate set to 0.")
# # #                     else:
# # #                         estimate_for_new = adj_new_estimate
# # #                         logger.info(f"Adding new category '{adj_item.category_name}' with estimate {estimate_for_new}.")
# # #                         categories_explicitly_adjusted_or_added.add(adj_item.category_name)
                    
# # #                     new_cat_data = {
# # #                         "category_name": adj_item.category_name,
# # #                         "estimated_amount": estimate_for_new,
# # #                         "percentage": 0.0  # Will be recalculated later
# # #                     }
                    
# # #                     # Add optional fields if they exist in the model
# # #                     if adj_actual_cost is not None:
# # #                         new_cat_data["actual_cost"] = adj_actual_cost
# # #                     if payment_status is not None:
# # #                         new_cat_data["payment_status"] = payment_status
                    
# # #                     new_cat_obj = BudgetCategoryBreakdown(**new_cat_data)
# # #                     working_categories_map[adj_item.category_name] = new_cat_obj
                
# # #             else:
# # #                 logger.warning(f"Skipping adjustment for '{adj_item.category_name}' as it was marked for deletion.")

# # #     # --- Step 4: Handle Redistribution ---
# # #     if not working_categories_map: # All categories were deleted
# # #         logger.info("All categories removed. Budget breakdown will be empty.")
# # #         plan.budget_breakdown = []
        
# # #         # Determine total budget behavior when all categories are deleted
# # #         if user_explicitly_set_total_budget:
# # #             # User set a specific total budget - maintain it
# # #             plan.current_total_budget = effective_total_budget
# # #             logger.info(f"All categories deleted. Maintaining user-specified total budget: {effective_total_budget}")
# # #         else:
# # #             # No explicit total budget set - maintain original budget
# # #             plan.current_total_budget = effective_total_budget  # This is the original budget
# # #             logger.info(f"All categories deleted. Maintaining original total budget: {effective_total_budget}")
        
# # #         # When all categories are deleted, total_spent should be 0 (no categories = no spending)
# # #         # But we need to account for any actual costs that were previously recorded
# # #         if deleted_actual_cost > 0:
# # #             logger.info(f"All categories deleted had combined actual costs of {deleted_actual_cost}. "
# # #                        f"Setting total_spent to 0 and adding deleted costs to balance.")
        
# # #         plan.total_spent = 0.0  # No categories = no spending
# # #         plan.balance = plan.current_total_budget  # All budget becomes available balance
        
# # #         logger.info(f"All categories deleted result: "
# # #                    f"Total Budget={plan.current_total_budget}, "
# # #                    f"Total Spent=0, Balance={plan.balance}, "
# # #                    f"Deleted Actual Costs={deleted_actual_cost}")
# # #     else:
# # #         # If user did NOT explicitly set a new total budget, redistribute deleted amounts
# # #         if not user_explicitly_set_total_budget and deleted_estimated_amount > 0:
# # #             logger.info(f"Redistributing deleted amount of {deleted_estimated_amount} among remaining categories")
            
# # #             # Get untouched categories (those not explicitly adjusted)
# # #             untouched_categories = {
# # #                 cat_name: cat_obj for cat_name, cat_obj in working_categories_map.items()
# # #                 if cat_name not in categories_explicitly_adjusted_or_added
# # #             }
            
# # #             if untouched_categories:
# # #                 # Calculate current total of untouched categories
# # #                 current_untouched_total = sum(cat.estimated_amount for cat in untouched_categories.values())
                
# # #                 if current_untouched_total > 0:
# # #                     # Proportional redistribution
# # #                     for cat_name, cat_obj in untouched_categories.items():
# # #                         proportion = cat_obj.estimated_amount / current_untouched_total
# # #                         additional_amount = deleted_estimated_amount * proportion
# # #                         cat_obj.estimated_amount = round(cat_obj.estimated_amount + additional_amount, 2)
# # #                         logger.info(f"Redistributed {additional_amount} to '{cat_name}', new amount: {cat_obj.estimated_amount}")
# # #                 else:
# # #                     # Equal distribution among untouched categories
# # #                     amount_per_category = deleted_estimated_amount / len(untouched_categories)
# # #                     for cat_name, cat_obj in untouched_categories.items():
# # #                         cat_obj.estimated_amount = round(cat_obj.estimated_amount + amount_per_category, 2)
# # #                         logger.info(f"Equally distributed {amount_per_category} to '{cat_name}', new amount: {cat_obj.estimated_amount}")
# # #             else:
# # #                 # No untouched categories, add to balance
# # #                 logger.info(f"No untouched categories to redistribute to. Amount {deleted_estimated_amount} will go to balance.")
        
# # #         # Identify categories whose estimates were NOT explicitly set in this request
# # #         untouched_remaining_categories: Dict[str, float] = {}
# # #         for cat_name, cat_obj in working_categories_map.items():
# # #             if cat_name not in categories_explicitly_adjusted_or_added:
# # #                 untouched_remaining_categories[cat_name] = cat_obj.estimated_amount

# # #         # Calculate the sum of estimates for categories that were explicitly set/added
# # #         sum_of_explicitly_set_or_added = sum(
# # #             working_categories_map[name].estimated_amount 
# # #             for name in categories_explicitly_adjusted_or_added 
# # #             if name in working_categories_map
# # #         )

# # #         if user_explicitly_set_total_budget:
# # #             # User explicitly set a new total budget
# # #             plan.current_total_budget = effective_total_budget
# # #             logger.info(f"Using user-specified total budget: {effective_total_budget}")
            
# # #             # Determine how much budget is left for untouched categories
# # #             budget_for_untouched = round(effective_total_budget - sum_of_explicitly_set_or_added, 2)
            
# # #             if untouched_remaining_categories:
# # #                 sum_of_original_estimates_of_untouched = sum(untouched_remaining_categories.values())

# # #                 if budget_for_untouched < 0:
# # #                     logger.warning(f"Budget for untouched categories ({budget_for_untouched}) is negative. Setting them to 0.")
# # #                     for cat_name in untouched_remaining_categories.keys():
# # #                         working_categories_map[cat_name].estimated_amount = 0.0
# # #                 elif sum_of_original_estimates_of_untouched > 0:
# # #                     # Proportional redistribution
# # #                     for cat_name, original_est in untouched_remaining_categories.items():
# # #                         proportion = original_est / sum_of_original_estimates_of_untouched
# # #                         new_val = round(budget_for_untouched * proportion, 2)
# # #                         working_categories_map[cat_name].estimated_amount = max(0.0, new_val)
# # #                 elif budget_for_untouched > 0:
# # #                     # Equal distribution if original sum was 0
# # #                     amount_per_cat = round(budget_for_untouched / len(untouched_remaining_categories), 2)
# # #                     for cat_name in untouched_remaining_categories.keys():
# # #                         working_categories_map[cat_name].estimated_amount = max(0.0, amount_per_cat)
# # #         else:
# # #             # Keep the original total budget (key change here)
# # #             plan.current_total_budget = effective_total_budget
# # #             logger.info(f"Maintaining original total budget: {effective_total_budget}")

# # #         # Reconstruct the final budget_breakdown list, preserving original order
# # #         final_breakdown_list: List[BudgetCategoryBreakdown] = []
# # #         original_order_names = [cat.category_name for cat in plan.budget_breakdown]

# # #         # Add categories that were in the original plan and still exist
# # #         for cat_name in original_order_names:
# # #             if cat_name in working_categories_map:
# # #                 final_breakdown_list.append(working_categories_map[cat_name])
        
# # #         # Add new categories
# # #         for cat_name, cat_obj in working_categories_map.items():
# # #             if cat_name not in original_order_names:
# # #                 final_breakdown_list.append(cat_obj)
        
# # #         plan.budget_breakdown = final_breakdown_list

# # #         # Adjust total_spent by removing deleted actual costs
# # #         if deleted_actual_cost > 0:
# # #             plan.total_spent = max(0.0, plan.total_spent - deleted_actual_cost)
# # #             logger.info(f"Adjusted total_spent by removing deleted actual costs: -{deleted_actual_cost}")

# # #     # --- Step 5: Recalculate Percentages, Total Spent, and Balance ---
# # #     if plan.current_total_budget > 0:
# # #         for item in plan.budget_breakdown:
# # #             item.percentage = round((item.estimated_amount / plan.current_total_budget) * 100, 2)
# # #     else:
# # #         for item in plan.budget_breakdown:
# # #             item.percentage = 0.0

# # #     # Recalculate total_spent based on remaining categories
# # #     remaining_actual_costs = 0.0
# # #     for cat in plan.budget_breakdown:
# # #         if hasattr(cat, 'actual_cost') and cat.actual_cost is not None:
# # #             remaining_actual_costs += cat.actual_cost
    
# # #     plan.total_spent = round(remaining_actual_costs, 2)
# # #     plan.balance = round(plan.current_total_budget - plan.total_spent, 2)
# # #     plan.timestamp = datetime.now(timezone.utc)

# # #     logger.info(f"Final plan state for {reference_id}: Total Budget={plan.current_total_budget}, "
# # #                 f"Sum of Estimates={round(sum(c.estimated_amount for c in plan.budget_breakdown), 2)}, "
# # #                 f"Total Spent={plan.total_spent}, Balance={plan.balance}")

# # #     # Save the updated plan to the database
# # #     document_to_db = plan.model_dump() 
# # #     try:
# # #         db[BUDGET_PLANS_COLLECTION].update_one({"reference_id": reference_id}, {"$set": document_to_db})
# # #         logger.info(f"Batch budget adjustments processed and saved for reference_id: {reference_id}")
# # #     except Exception as e:
# # #         logger.error(f"Error saving batch adjusted budget plan for reference_id: {reference_id} to DB: {e}", exc_info=True)
# # #         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save batch adjusted budget plan.")

# # #     return plan 


# # # weddingverse_api15/app/services/batch_adjust_service.py
# # from datetime import datetime, timezone
# # from typing import List, Dict
# # from fastapi import HTTPException, status
# # from app.models.budget import (
# #     BudgetPlanDBSchema,
# #     BudgetCategoryBreakdown,
# #     BatchAdjustEstimatesFixedTotalRequest
# # )
# # from app.services.mongo_service import db
# # from app.utils.logger import logger

# # BUDGET_PLANS_COLLECTION = "budget_plans"
# # REMAINING_BUDGET_CATEGORY_NAME = "Other Expenses / Unallocated"

# # # NEW: Mapping from budget category names to vendor collection names
# # # This is crucial for synchronizing deletions between budget breakdown and selected vendors.
# # BUDGET_CATEGORY_TO_VENDOR_COLLECTION_MAP = {
# #     "Venue": "venues",
# #     "Caterer": "catering",
# #     "Photography": "photographers",
# #     "Makeup": "makeups",
# #     "DJ": "djs",
# #     "Decor": "decors",
# #     "Mehendi": "mehendi",
# #     "Bridal Wear": "bridal_wear",
# #     "Wedding Invitations": "weddingInvitations",
# #     "Honeymoon": "honeymoon",
# #     "Car": "car",
# #     "Astrology": "astro", # Assuming "Astrology" is the budget category for "astro" collection
# #     "Jewellery": "jewellery",
# #     "Wedding Planner": "wedding_planner",
# #     # Add any other budget categories and their corresponding vendor collection names here.
# #     # If a budget category has no corresponding vendor collection (e.g., "Contingency"),
# #     # it doesn't need to be in this map.
# # }


# # def process_batch_adjustments_fixed_total(
# #     reference_id: str,
# #     request_data: BatchAdjustEstimatesFixedTotalRequest
# # ) -> BudgetPlanDBSchema:
# #     """
# #     Process batch adjustments including updates, additions, and deletions.
    
# #     Deletion Behavior:
# #     1. Single category deleted: Amount redistributed to remaining categories, total budget unchanged
# #     2. Multiple categories deleted: Combined amounts redistributed to remaining categories
# #     3. ALL categories deleted: 
# #        - Budget breakdown becomes empty []
# #        - Total budget maintained (original or user-specified)
# #        - Total spent becomes 0 (no categories = no spending)
# #        - Balance becomes equal to total budget (everything available)
# #        - Any actual costs from deleted categories are effectively "refunded"
    
# #     Example - All categories deleted:
# #     Before: Total=30000, Venue=15000(paid 12000), Caterer=10000(paid 5000), DJ=5000(unpaid)
# #     After:  Total=30000, Categories=[], Spent=0, Balance=30000
# #     Result: User gets full budget back as available balance
# #     """
# #     logger.info(f"Processing batch adjustments for plan_id: {reference_id}")

# #     # Fetch the existing budget plan using 'reference_id'
# #     plan_dict = db[BUDGET_PLANS_COLLECTION].find_one({"reference_id": reference_id})
# #     if not plan_dict:
# #         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Budget plan with reference_id '{reference_id}' not found.")

# #     try:
# #         # Validate and load the existing plan
# #         plan = BudgetPlanDBSchema.model_validate(plan_dict)
# #     except Exception as e:
# #         logger.error(f"Data validation error for existing plan {reference_id}: {e}")
# #         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error validating existing budget plan data.")

# #     # --- Determine the effective total budget for this operation ---
# #     effective_total_budget: float
# #     user_explicitly_set_total_budget = False
# #     if request_data.new_total_budget is not None and request_data.new_total_budget > 0:
# #         effective_total_budget = round(request_data.new_total_budget, 2)
# #         user_explicitly_set_total_budget = True
# #         logger.info(f"Request to change total budget to: {effective_total_budget}")
# #     else:
# #         # Keep the original total budget - this is key for proper redistribution
# #         effective_total_budget = plan.current_total_budget
# #         logger.info(f"Using existing total budget: {effective_total_budget}")

# #     # --- Step 1: Initialize working_categories_map with current plan's categories ---
# #     working_categories_map: Dict[str, BudgetCategoryBreakdown] = {
# #         cat.category_name: cat.model_copy() for cat in plan.budget_breakdown
# #     }
    
# #     # --- Step 2: Process Deletions and handle actual costs ---
# #     categories_to_be_deleted_names = {
# #         del_item.category_name for del_item in request_data.deletions 
# #         if del_item.category_name.lower() not in ["string", "example", "placeholder", "test"] # Skip placeholders
# #     }
    
# #     # Track deleted amounts and actual costs for redistribution
# #     deleted_estimated_amount = 0.0
# #     deleted_actual_cost = 0.0
    
# #     for cat_name in categories_to_be_deleted_names:
# #         if cat_name in working_categories_map:
# #             deleted_category = working_categories_map[cat_name]
# #             deleted_estimated_amount += deleted_category.estimated_amount
            
# #             # Handle actual cost of deleted category
# #             if deleted_category.actual_cost is not None and deleted_category.actual_cost > 0:
# #                 deleted_actual_cost += deleted_category.actual_cost
# #                 logger.info(f"Deleted category '{cat_name}' had actual cost of {deleted_category.actual_cost}")
            
# #             logger.info(f"Deleting category '{cat_name}' with estimated amount {deleted_category.estimated_amount}")
# #             del working_categories_map[cat_name]
# #         else:
# #             logger.warning(f"Category '{cat_name}' requested for deletion not found in current plan estimates.")

# #     # --- UPDATED LOGIC: Step 2.5: Remove selected vendors for deleted categories ---
# #     if categories_to_be_deleted_names:
# #         original_selected_vendors_count = len(plan.selected_vendors)
        
# #         # Determine which vendor collection names correspond to the budget categories being deleted
# #         vendor_collections_to_delete_from_selected = set()
# #         for budget_cat_name in categories_to_be_deleted_names:
# #             vendor_collection_name = BUDGET_CATEGORY_TO_VENDOR_COLLECTION_MAP.get(budget_cat_name)
# #             if vendor_collection_name:
# #                 vendor_collections_to_delete_from_selected.add(vendor_collection_name)
# #             else:
# #                 logger.warning(f"No vendor collection mapping found for budget category '{budget_cat_name}'. Selected vendors for this category will not be automatically deleted.")

# #         if vendor_collections_to_delete_from_selected:
# #             # Filter out selected vendors whose category_name is in the determined set
# #             plan.selected_vendors = [
# #                 vendor for vendor in plan.selected_vendors
# #                 if vendor.category_name not in vendor_collections_to_delete_from_selected
# #             ]
# #             deleted_selected_vendors_count = original_selected_vendors_count - len(plan.selected_vendors)
# #             if deleted_selected_vendors_count > 0:
# #                 logger.info(f"Removed {deleted_selected_vendors_count} selected vendor(s) associated with deleted budget categories: {vendor_collections_to_delete_from_selected}.")
# #             else:
# #                 logger.info(f"No selected vendors found for the deleted budget categories: {vendor_collections_to_delete_from_selected}.")
# #         else:
# #             logger.info("No corresponding vendor collections found for the deleted budget categories. No selected vendors removed.")
# #     # --- END UPDATED LOGIC ---

# #     # --- Step 3: Process Adjustments (Updates and Additions) ---
# #     categories_explicitly_adjusted_or_added = set()
    
# #     if request_data.adjustments:
# #         for adj_item in request_data.adjustments:
# #             if adj_item.category_name.lower() in ["string", "example", "placeholder", "test"]:
# #                 logger.info(f"Skipping placeholder adjustment category name: '{adj_item.category_name}'")
# #                 continue
            
# #             # Get actual_cost and payment_status with proper attribute access
# #             actual_cost = getattr(adj_item, 'actual_cost', None)
# #             payment_status = getattr(adj_item, 'payment_status', None)
            
# #             # Determine if this is just an actual_cost/payment_status update
# #             # If new_estimate is 0 AND we have actual_cost or payment_status, treat as cost-only update
# #             is_cost_only_update = (
# #                 adj_item.new_estimate == 0 and 
# #                 (actual_cost is not None or payment_status is not None)
# #             )
            
# #             # Skip if no meaningful change (truly empty adjustment)
# #             if adj_item.new_estimate == 0 and actual_cost is None and payment_status is None:
# #                 logger.info(f"Skipping adjustment for '{adj_item.category_name}' as no meaningful change.")
# #                 continue

# #             # Estimates cannot be negative
# #             if adj_item.new_estimate < 0:
# #                 raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Estimate for category '{adj_item.category_name}' cannot be negative.")
            
# #             # Actual cost cannot be negative if provided
# #             if actual_cost is not None and actual_cost < 0:
# #                  raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Actual cost for category '{adj_item.category_name}' cannot be negative.")

# #             adj_new_estimate = round(adj_item.new_estimate, 2) if not is_cost_only_update else None
# #             adj_actual_cost = round(actual_cost, 2) if actual_cost is not None else None

# #             if adj_item.category_name not in categories_to_be_deleted_names:
# #                 if adj_item.category_name in working_categories_map: # Update existing category
# #                     cat_obj = working_categories_map[adj_item.category_name]
                    
# #                     if is_cost_only_update:
# #                         # Only update actual_cost and payment_status, keep existing estimate
# #                         logger.info(f"Updating only actual_cost/payment_status for '{adj_item.category_name}'. "
# #                                    f"Estimate remains: {cat_obj.estimated_amount}")
# #                         # Don't add to explicitly adjusted categories since estimate wasn't changed
# #                     else:
# #                         # Update the estimate
# #                         logger.info(f"Updating category '{adj_item.category_name}' estimate from {cat_obj.estimated_amount} to {adj_new_estimate}.")
# #                         cat_obj.estimated_amount = adj_new_estimate
# #                         categories_explicitly_adjusted_or_added.add(adj_item.category_name)
                    
# #                     # Always update actual_cost and payment_status if provided
# #                     if hasattr(cat_obj, 'actual_cost'):
# #                         cat_obj.actual_cost = adj_actual_cost
# #                     if hasattr(cat_obj, 'payment_status'):
# #                         cat_obj.payment_status = payment_status
                        
# #                 else: # Add new category
# #                     if is_cost_only_update:
# #                         # For new categories, if it's cost-only update, set estimate to 0
# #                         estimate_for_new = 0.0
# #                         logger.info(f"Adding new category '{adj_item.category_name}' with cost-only update. Estimate set to 0.")
# #                     else:
# #                         estimate_for_new = adj_new_estimate
# #                         logger.info(f"Adding new category '{adj_item.category_name}' with estimate {estimate_for_new}.")
# #                         categories_explicitly_adjusted_or_added.add(adj_item.category_name)
                    
# #                     new_cat_data = {
# #                         "category_name": adj_item.category_name,
# #                         "estimated_amount": estimate_for_new,
# #                         "percentage": 0.0  # Will be recalculated later
# #                     }
                    
# #                     # Add optional fields if they exist in the model
# #                     if adj_actual_cost is not None:
# #                         new_cat_data["actual_cost"] = adj_actual_cost
# #                     if payment_status is not None:
# #                         new_cat_data["payment_status"] = payment_status
                    
# #                     new_cat_obj = BudgetCategoryBreakdown(**new_cat_data)
# #                     working_categories_map[adj_item.category_name] = new_cat_obj
                
# #             else:
# #                 logger.warning(f"Skipping adjustment for '{adj_item.category_name}' as it was marked for deletion.")

# #     # --- Step 4: Handle Redistribution ---
# #     if not working_categories_map: # All categories were deleted
# #         logger.info("All categories removed. Budget breakdown will be empty.")
# #         plan.budget_breakdown = []
        
# #         # Determine total budget behavior when all categories are deleted
# #         if user_explicitly_set_total_budget:
# #             # User set a specific total budget - maintain it
# #             plan.current_total_budget = effective_total_budget
# #             logger.info(f"All categories deleted. Maintaining user-specified total budget: {effective_total_budget}")
# #         else:
# #             # No explicit total budget set - maintain original budget
# #             plan.current_total_budget = effective_total_budget  # This is the original budget
# #             logger.info(f"All categories deleted. Maintaining original total budget: {effective_total_budget}")
        
# #         # When all categories are deleted, total_spent should be 0 (no categories = no spending)
# #         # But we need to account for any actual costs that were previously recorded
# #         if deleted_actual_cost > 0:
# #             logger.info(f"All categories deleted had combined actual costs of {deleted_actual_cost}. "
# #                        f"Setting total_spent to 0 and adding deleted costs to balance.")
        
# #         plan.total_spent = 0.0  # No categories = no spending
# #         plan.balance = plan.current_total_budget  # All budget becomes available balance
        
# #         logger.info(f"All categories deleted result: "
# #                    f"Total Budget={plan.current_total_budget}, "
# #                    f"Total Spent=0, Balance={plan.balance}, "
# #                    f"Deleted Actual Costs={deleted_actual_cost}")
# #     else:
# #         # If user did NOT explicitly set a new total budget, redistribute deleted amounts
# #         if not user_explicitly_set_total_budget and deleted_estimated_amount > 0:
# #             logger.info(f"Redistributing deleted amount of {deleted_estimated_amount} among remaining categories")
            
# #             # Get untouched categories (those not explicitly adjusted)
# #             untouched_categories = {
# #                 cat_name: cat_obj for cat_name, cat_obj in working_categories_map.items()
# #                 if cat_name not in categories_explicitly_adjusted_or_added
# #             }
            
# #             if untouched_categories:
# #                 # Calculate current total of untouched categories
# #                 current_untouched_total = sum(cat.estimated_amount for cat in untouched_categories.values())
                
# #                 if current_untouched_total > 0:
# #                     # Proportional redistribution
# #                     for cat_name, cat_obj in untouched_categories.items():
# #                         proportion = cat_obj.estimated_amount / current_untouched_total
# #                         additional_amount = deleted_estimated_amount * proportion
# #                         cat_obj.estimated_amount = round(cat_obj.estimated_amount + additional_amount, 2)
# #                         logger.info(f"Redistributed {additional_amount} to '{cat_name}', new amount: {cat_obj.estimated_amount}")
# #                 else:
# #                     # Equal distribution among untouched categories
# #                     amount_per_category = deleted_estimated_amount / len(untouched_categories)
# #                     for cat_name, cat_obj in untouched_categories.items():
# #                         cat_obj.estimated_amount = round(cat_obj.estimated_amount + amount_per_category, 2)
# #                         logger.info(f"Equally distributed {amount_per_category} to '{cat_name}', new amount: {cat_obj.estimated_amount}")
# #             else:
# #                 # No untouched categories, amount will go to balance after final recalculations
# #                 logger.info(f"No untouched categories to redistribute to. Amount {deleted_estimated_amount} will implicitly go to balance.")
        
# #         # Identify categories whose estimates were NOT explicitly set in this request
# #         untouched_remaining_categories: Dict[str, float] = {}
# #         for cat_name, cat_obj in working_categories_map.items():
# #             if cat_name not in categories_explicitly_adjusted_or_added:
# #                 untouched_remaining_categories[cat_name] = cat_obj.estimated_amount

# #         if user_explicitly_set_total_budget:
# #             # User explicitly set a new total budget
# #             plan.current_total_budget = effective_total_budget
# #             logger.info(f"Using user-specified total budget: {effective_total_budget}")
            
# #             # Determine how much budget is left for untouched categories
# #             budget_for_untouched = round(effective_total_budget - sum_of_explicitly_set_or_added, 2)
            
# #             if untouched_remaining_categories:
# #                 sum_of_original_estimates_of_untouched = sum(untouched_remaining_categories.values())

# #                 if budget_for_untouched < 0:
# #                     logger.warning(f"Budget for untouched categories ({budget_for_untouched}) is negative due to new total budget. Setting them to 0.")
# #                     for cat_name in untouched_remaining_categories.keys():
# #                         working_categories_map[cat_name].estimated_amount = 0.0
# #                 elif sum_of_original_estimates_of_untouched > 0:
# #                     # Proportional redistribution
# #                     for cat_name, original_est in untouched_remaining_categories.items():
# #                         # Avoid ZeroDivisionError if sum_of_original_estimates_of_untouched is 0
# #                         proportion = original_est / sum_of_original_estimates_of_untouched if sum_of_original_estimates_of_untouched > 0 else 0
# #                         new_val = round(budget_for_untouched * proportion, 2)
# #                         working_categories_map[cat_name].estimated_amount = max(0.0, new_val)
# #                 elif budget_for_untouched > 0:
# #                     # Equal distribution if original sum was 0 (and budget_for_untouched is positive)
# #                     amount_per_cat = round(budget_for_untouched / len(untouched_remaining_categories), 2)
# #                     for cat_name in untouched_remaining_categories.keys():
# #                         working_categories_map[cat_name].estimated_amount = max(0.0, amount_per_cat)
# #             else:
# #                 # If no untouched categories, the remaining budget just contributes to balance
# #                 logger.info("No untouched categories to adjust. Remaining budget will implicitly go to balance.")
# #         else:
# #             # Keep the original total budget (key change here)
# #             plan.current_total_budget = effective_total_budget
# #             logger.info(f"Maintaining original total budget: {effective_total_budget}")

# #         # Reconstruct the final budget_breakdown list, preserving original order
# #         final_breakdown_list: List[BudgetCategoryBreakdown] = []
# #         original_order_names = [cat.category_name for cat in plan.budget_breakdown]

# #         # Add categories that were in the original plan and still exist
# #         for cat_name in original_order_names:
# #             if cat_name in working_categories_map:
# #                 final_breakdown_list.append(working_categories_map[cat_name])
        
# #         # Add new categories (those that were added in this request)
# #         for cat_name, cat_obj in working_categories_map.items():
# #             # Check if this is a newly added category, or an existing one that was explicitly adjusted
# #             if cat_name not in original_order_names and cat_name not in categories_to_be_deleted_names: # Ensure it's not a deleted category or already handled
# #                 final_breakdown_list.append(cat_obj)
        
# #         plan.budget_breakdown = final_breakdown_list

# #         # Adjust total_spent by removing deleted actual costs
# #         if deleted_actual_cost > 0:
# #             plan.total_spent = max(0.0, plan.total_spent - deleted_actual_cost)
# #             logger.info(f"Adjusted total_spent by removing deleted actual costs: -{deleted_actual_cost}")

# #     # --- Step 5: Recalculate Percentages, Total Spent, and Balance ---
# #     if plan.current_total_budget > 0:
# #         for item in plan.budget_breakdown:
# #             item.percentage = round((item.estimated_amount / plan.current_total_budget) * 100, 2)
# #     else:
# #         for item in plan.budget_breakdown:
# #             item.percentage = 0.0

# #     # Recalculate total_spent based on remaining categories
# #     remaining_actual_costs = 0.0
# #     for cat in plan.budget_breakdown:
# #         if hasattr(cat, 'actual_cost') and cat.actual_cost is not None:
# #             remaining_actual_costs += cat.actual_cost
    
# #     plan.total_spent = round(remaining_actual_costs, 2)
# #     plan.balance = round(plan.current_total_budget - plan.total_spent, 2)
# #     plan.timestamp = datetime.now(timezone.utc)

# #     logger.info(f"Final plan state for {reference_id}: Total Budget={plan.current_total_budget}, "
# #                 f"Sum of Estimates={round(sum(c.estimated_amount for c in plan.budget_breakdown), 2)}, "
# #                 f"Total Spent={plan.total_spent}, Balance={plan.balance}")

# #     # Save the updated plan to the database
# #     document_to_db = plan.model_dump() 
# #     try:
# #         db[BUDGET_PLANS_COLLECTION].update_one({"reference_id": reference_id}, {"$set": document_to_db})
# #         logger.info(f"Batch budget adjustments processed and saved for reference_id: {reference_id}")
# #     except Exception as e:
# #         logger.error(f"Error saving batch adjusted budget plan for reference_id: {reference_id} to DB: {e}", exc_info=True)
# #         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save batch adjusted budget plan.")

# #     return plan 



# # app/services/budget_service.py
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

# # NEW: Mapping from budget category names to vendor collection names
# # This is crucial for synchronizing deletions between budget breakdown and selected vendors.
# BUDGET_CATEGORY_TO_VENDOR_COLLECTION_MAP = {
#     "Venue": "venues",
#     "Caterer": "catering",
#     "Photography": "photographers",
#     "Makeup": "makeups",
#     "DJ": "djs",
#     "Decor": "decors",
#     "Mehendi": "mehendi",
#     "Bridal Wear": "bridal_wear",
#     "Wedding Invitations": "weddingInvitations",
#     "Honeymoon": "honeymoon",
#     "Car": "car",
#     "Astrology": "astro", # Assuming "Astrology" is the budget category for "astro" collection
#     "Jewellery": "jewellery",
#     "Wedding Planner": "wedding_planner",
#     # Add any other budget categories and their corresponding vendor collection names here.
#     # If a budget category has no corresponding vendor collection (e.g., "Contingency"),
#     # it doesn't need to be in this map.
# }


# def process_batch_adjustments_fixed_total(
#     reference_id: str,
#     request_data: BatchAdjustEstimatesFixedTotalRequest
# ) -> BudgetPlanDBSchema:
#     """
#     Process batch adjustments including updates, additions, and deletions.
    
#     Deletion Behavior:
#     1. Single category deleted: Amount redistributed to remaining categories, total budget unchanged
#     2. Multiple categories deleted: Combined amounts redistributed to remaining categories
#     3. ALL categories deleted: 
#        - Budget breakdown becomes empty []
#        - Total budget maintained (original or user-specified)
#        - Total spent becomes 0 (no categories = no spending)
#        - Balance becomes equal to total budget (everything available)
#        - Any actual costs from deleted categories are effectively "refunded"
    
#     Example - All categories deleted:
#     Before: Total=30000, Venue=15000(paid 12000), Caterer=10000(paid 5000), DJ=5000(unpaid)
#     After:  Total=30000, Categories=[], Spent=0, Balance=30000
#     Result: User gets full budget back as available balance
#     """
#     logger.info(f"Processing batch adjustments for plan_id: {reference_id}")

#     # Fetch the existing budget plan using 'reference_id'
#     plan_dict = db[BUDGET_PLANS_COLLECTION].find_one({"reference_id": reference_id})
#     if not plan_dict:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Budget plan with reference_id '{reference_id}' not found.")

#     try:
#         # Validate and load the existing plan
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
#         # Keep the original total budget - this is key for proper redistribution
#         effective_total_budget = plan.current_total_budget
#         logger.info(f"Using existing total budget: {effective_total_budget}")

#     # --- Step 1: Initialize working_categories_map with current plan's categories ---
#     working_categories_map: Dict[str, BudgetCategoryBreakdown] = {
#         cat.category_name: cat.model_copy() for cat in plan.budget_breakdown
#     }
    
#     # --- Step 2: Process Deletions and handle actual costs ---
#     categories_to_be_deleted_names = {
#         del_item.category_name for del_item in request_data.deletions 
#         if del_item.category_name.lower() not in ["string", "example", "placeholder", "test"] # Skip placeholders
#     }
    
#     # Track deleted amounts and actual costs for redistribution
#     deleted_estimated_amount = 0.0
#     deleted_actual_cost = 0.0
    
#     for cat_name in categories_to_be_deleted_names:
#         if cat_name in working_categories_map:
#             deleted_category = working_categories_map[cat_name]
#             deleted_estimated_amount += deleted_category.estimated_amount
            
#             # Handle actual cost of deleted category
#             if deleted_category.actual_cost is not None and deleted_category.actual_cost > 0:
#                 deleted_actual_cost += deleted_category.actual_cost
#                 logger.info(f"Deleted category '{cat_name}' had actual cost of {deleted_category.actual_cost}")
            
#             logger.info(f"Deleting category '{cat_name}' with estimated amount {deleted_category.estimated_amount}")
#             del working_categories_map[cat_name]
#         else:
#             logger.warning(f"Category '{cat_name}' requested for deletion not found in current plan estimates.")

#     # --- UPDATED LOGIC: Step 2.5: Remove selected vendors for deleted categories ---
#     if categories_to_be_deleted_names:
#         original_selected_vendors_count = len(plan.selected_vendors)
        
#         # Determine which vendor collection names correspond to the budget categories being deleted
#         vendor_collections_to_delete_from_selected = set()
#         for budget_cat_name in categories_to_be_deleted_names:
#             vendor_collection_name = BUDGET_CATEGORY_TO_VENDOR_COLLECTION_MAP.get(budget_cat_name)
#             if vendor_collection_name:
#                 vendor_collections_to_delete_from_selected.add(vendor_collection_name)
#             else:
#                 logger.warning(f"No vendor collection mapping found for budget category '{budget_cat_name}'. Selected vendors for this category will not be automatically deleted.")

#         if vendor_collections_to_delete_from_selected:
#             # Filter out selected vendors whose category_name is in the determined set
#             plan.selected_vendors = [
#                 vendor for vendor in plan.selected_vendors
#                 if vendor.category_name not in vendor_collections_to_delete_from_selected
#             ]
#             deleted_selected_vendors_count = original_selected_vendors_count - len(plan.selected_vendors)
#             if deleted_selected_vendors_count > 0:
#                 logger.info(f"Removed {deleted_selected_vendors_count} selected vendor(s) associated with deleted budget categories: {vendor_collections_to_delete_from_selected}.")
#             else:
#                 logger.info(f"No selected vendors found for the deleted budget categories: {vendor_collections_to_delete_from_selected}.")
#         else:
#             logger.info("No corresponding vendor collections found for the deleted budget categories. No selected vendors removed.")
#     # --- END UPDATED LOGIC ---

#     # --- Step 3: Process Adjustments (Updates and Additions) ---
#     categories_explicitly_adjusted_or_added = set()
    
#     if request_data.adjustments:
#         for adj_item in request_data.adjustments:
#             if adj_item.category_name.lower() in ["string", "example", "placeholder", "test"]:
#                 logger.info(f"Skipping placeholder adjustment category name: '{adj_item.category_name}'")
#                 continue
            
#             # Get actual_cost and payment_status with proper attribute access
#             actual_cost = getattr(adj_item, 'actual_cost', None)
#             payment_status = getattr(adj_item, 'payment_status', None)
            
#             # Determine if this is just an actual_cost/payment_status update
#             # If new_estimate is 0 AND we have actual_cost or payment_status, treat as cost-only update
#             is_cost_only_update = (
#                 adj_item.new_estimate == 0 and 
#                 (actual_cost is not None or payment_status is not None)
#             )
            
#             # Skip if no meaningful change (truly empty adjustment)
#             if adj_item.new_estimate == 0 and actual_cost is None and payment_status is None:
#                 logger.info(f"Skipping adjustment for '{adj_item.category_name}' as no meaningful change.")
#                 continue

#             # Estimates cannot be negative
#             if adj_item.new_estimate < 0:
#                 raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Estimate for category '{adj_item.category_name}' cannot be negative.")
            
#             # Actual cost cannot be negative if provided
#             if actual_cost is not None and actual_cost < 0:
#                  raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Actual cost for category '{adj_item.category_name}' cannot be negative.")

#             adj_new_estimate = round(adj_item.new_estimate, 2) if not is_cost_only_update else None
#             adj_actual_cost = round(actual_cost, 2) if actual_cost is not None else None

#             if adj_item.category_name not in categories_to_be_deleted_names:
#                 if adj_item.category_name in working_categories_map: # Update existing category
#                     cat_obj = working_categories_map[adj_item.category_name]
                    
#                     if is_cost_only_update:
#                         # Only update actual_cost and payment_status, keep existing estimate
#                         logger.info(f"Updating only actual_cost/payment_status for '{adj_item.category_name}'. "
#                                    f"Estimate remains: {cat_obj.estimated_amount}")
#                         # Don't add to explicitly adjusted categories since estimate wasn't changed
#                     else:
#                         # Update the estimate
#                         logger.info(f"Updating category '{adj_item.category_name}' estimate from {cat_obj.estimated_amount} to {adj_new_estimate}.")
#                         cat_obj.estimated_amount = adj_new_estimate
#                         categories_explicitly_adjusted_or_added.add(adj_item.category_name)
                    
#                     # Always update actual_cost and payment_status if provided
#                     if hasattr(cat_obj, 'actual_cost'):
#                         cat_obj.actual_cost = adj_actual_cost
#                     if hasattr(cat_obj, 'payment_status'):
#                         cat_obj.payment_status = payment_status
                        
#                 else: # Add new category
#                     if is_cost_only_update:
#                         # For new categories, if it's cost-only update, set estimate to 0
#                         estimate_for_new = 0.0
#                         logger.info(f"Adding new category '{adj_item.category_name}' with cost-only update. Estimate set to 0.")
#                     else:
#                         estimate_for_new = adj_new_estimate
#                         logger.info(f"Adding new category '{adj_item.category_name}' with estimate {estimate_for_new}.")
#                         categories_explicitly_adjusted_or_added.add(adj_item.category_name)
                    
#                     new_cat_data = {
#                         "category_name": adj_item.category_name,
#                         "estimated_amount": estimate_for_new,
#                         "percentage": 0.0  # Will be recalculated later
#                     }
                    
#                     # Add optional fields if they exist in the model
#                     if adj_actual_cost is not None:
#                         new_cat_data["actual_cost"] = adj_actual_cost
#                     if payment_status is not None:
#                         new_cat_data["payment_status"] = payment_status
                    
#                     new_cat_obj = BudgetCategoryBreakdown(**new_cat_data)
#                     working_categories_map[adj_item.category_name] = new_cat_obj
                
#             else:
#                 logger.warning(f"Skipping adjustment for '{adj_item.category_name}' as it was marked for deletion.")

#     # --- Step 4: Handle Redistribution ---
#     if not working_categories_map: # All categories were deleted
#         logger.info("All categories removed. Budget breakdown will be empty.")
#         plan.budget_breakdown = []
        
#         # Determine total budget behavior when all categories are deleted
#         if user_explicitly_set_total_budget:
#             # User set a specific total budget - maintain it
#             plan.current_total_budget = effective_total_budget
#             logger.info(f"All categories deleted. Maintaining user-specified total budget: {effective_total_budget}")
#         else:
#             # No explicit total budget set - maintain original budget
#             plan.current_total_budget = effective_total_budget  # This is the original budget
#             logger.info(f"All categories deleted. Maintaining original total budget: {effective_total_budget}")
        
#         # When all categories are deleted, total_spent should be 0 (no categories = no spending)
#         # But we need to account for any actual costs that were previously recorded
#         if deleted_actual_cost > 0:
#             logger.info(f"All categories deleted had combined actual costs of {deleted_actual_cost}. "
#                        f"Setting total_spent to 0 and adding deleted costs to balance.")
        
#         plan.total_spent = 0.0  # No categories = no spending
#         plan.balance = plan.current_total_budget  # All budget becomes available balance
        
#         logger.info(f"All categories deleted result: "
#                    f"Total Budget={plan.current_total_budget}, "
#                    f"Total Spent=0, Balance={plan.balance}, "
#                    f"Deleted Actual Costs={deleted_actual_cost}")
#     else:
#         # Calculate the sum of estimates for categories that were explicitly set/added
#         # This line MUST be here, outside the 'if user_explicitly_set_total_budget' block,
#         # but inside the 'else' block for working_categories_map (i.e., when categories remain).
#         sum_of_explicitly_set_or_added = sum(
#             working_categories_map[name].estimated_amount
#             for name in categories_explicitly_adjusted_or_added
#             if name in working_categories_map
#         )

#         # If user did NOT explicitly set a new total budget, redistribute deleted amounts
#         if not user_explicitly_set_total_budget and deleted_estimated_amount > 0:
#             logger.info(f"Redistributing deleted amount of {deleted_estimated_amount} among remaining categories")
            
#             # Get untouched categories (those not explicitly adjusted)
#             untouched_categories = {
#                 cat_name: cat_obj for cat_name, cat_obj in working_categories_map.items()
#                 if cat_name not in categories_explicitly_adjusted_or_added
#             }
            
#             if untouched_categories:
#                 # Calculate current total of untouched categories
#                 current_untouched_total = sum(cat.estimated_amount for cat in untouched_categories.values())
                
#                 if current_untouched_total > 0:
#                     # Proportional redistribution
#                     for cat_name, cat_obj in untouched_categories.items():
#                         proportion = cat_obj.estimated_amount / current_untouched_total
#                         additional_amount = deleted_estimated_amount * proportion
#                         cat_obj.estimated_amount = round(cat_obj.estimated_amount + additional_amount, 2)
#                         logger.info(f"Redistributed {additional_amount} to '{cat_name}', new amount: {cat_obj.estimated_amount}")
#                 else:
#                     # Equal distribution among untouched categories
#                     amount_per_category = deleted_estimated_amount / len(untouched_categories)
#                     for cat_name, cat_obj in untouched_categories.items():
#                         cat_obj.estimated_amount = round(cat_obj.estimated_amount + amount_per_category, 2)
#                         logger.info(f"Equally distributed {amount_per_category} to '{cat_name}', new amount: {cat_obj.estimated_amount}")
#             else:
#                 # No untouched categories, amount will go to balance after final recalculations
#                 logger.info(f"No untouched categories to redistribute to. Amount {deleted_estimated_amount} will implicitly go to balance.")
        
#         # Identify categories whose estimates were NOT explicitly set in this request
#         untouched_remaining_categories: Dict[str, float] = {}
#         for cat_name, cat_obj in working_categories_map.items():
#             if cat_name not in categories_explicitly_adjusted_or_added:
#                 untouched_remaining_categories[cat_name] = cat_obj.estimated_amount

#         if user_explicitly_set_total_budget:
#             # User explicitly set a new total budget
#             plan.current_total_budget = effective_total_budget
#             logger.info(f"Using user-specified total budget: {effective_total_budget}")
            
#             # Determine how much budget is left for untouched categories
#             budget_for_untouched = round(effective_total_budget - sum_of_explicitly_set_or_added, 2)
            
#             if untouched_remaining_categories:
#                 sum_of_original_estimates_of_untouched = sum(untouched_remaining_categories.values())

#                 if budget_for_untouched < 0:
#                     logger.warning(f"Budget for untouched categories ({budget_for_untouched}) is negative due to new total budget. Setting them to 0.")
#                     for cat_name in untouched_remaining_categories.keys():
#                         working_categories_map[cat_name].estimated_amount = 0.0
#                 elif sum_of_original_estimates_of_untouched > 0:
#                     # Proportional redistribution
#                     for cat_name, original_est in untouched_remaining_categories.items():
#                         # Avoid ZeroDivisionError if sum_of_original_estimates_of_untouched is 0
#                         proportion = original_est / sum_of_original_estimates_of_untouched if sum_of_original_estimates_of_untouched > 0 else 0
#                         new_val = round(budget_for_untouched * proportion, 2)
#                         working_categories_map[cat_name].estimated_amount = max(0.0, new_val)
#                 elif budget_for_untouched > 0:
#                     # Equal distribution if original sum was 0 (and budget_for_untouched is positive)
#                     amount_per_cat = round(budget_for_untouched / len(untouched_remaining_categories), 2)
#                     for cat_name in untouched_remaining_categories.keys():
#                         working_categories_map[cat_name].estimated_amount = max(0.0, amount_per_cat)
#             else:
#                 # If no untouched categories, the remaining budget just contributes to balance
#                 logger.info("No untouched categories to adjust. Remaining budget will implicitly go to balance.")
#         else:
#             # Keep the original total budget (key change here)
#             plan.current_total_budget = effective_total_budget
#             logger.info(f"Maintaining original total budget: {effective_total_budget}")

#         # Reconstruct the final budget_breakdown list, preserving original order
#         final_breakdown_list: List[BudgetCategoryBreakdown] = []
#         original_order_names = [cat.category_name for cat in plan.budget_breakdown]

#         # Add categories that were in the original plan and still exist
#         for cat_name in original_order_names:
#             if cat_name in working_categories_map:
#                 final_breakdown_list.append(working_categories_map[cat_name])
        
#         # Add new categories (those that were added in this request)
#         for cat_name, cat_obj in working_categories_map.items():
#             # Check if this is a newly added category, or an existing one that was explicitly adjusted
#             if cat_name not in original_order_names and cat_name not in categories_to_be_deleted_names: # Ensure it's not a deleted category or already handled
#                 final_breakdown_list.append(cat_obj)
        
#         plan.budget_breakdown = final_breakdown_list

#         # Adjust total_spent by removing deleted actual costs
#         if deleted_actual_cost > 0:
#             plan.total_spent = max(0.0, plan.total_spent - deleted_actual_cost)
#             logger.info(f"Adjusted total_spent by removing deleted actual costs: -{deleted_actual_cost}")

#     # --- Step 5: Recalculate Percentages, Total Spent, and Balance ---
#     if plan.current_total_budget > 0:
#         for item in plan.budget_breakdown:
#             item.percentage = round((item.estimated_amount / plan.current_total_budget) * 100, 2)
#     else:
#         for item in plan.budget_breakdown:
#             item.percentage = 0.0

#     # Recalculate total_spent based on remaining categories
#     remaining_actual_costs = 0.0
#     for cat in plan.budget_breakdown:
#         if hasattr(cat, 'actual_cost') and cat.actual_cost is not None:
#             remaining_actual_costs += cat.actual_cost
    
#     plan.total_spent = round(remaining_actual_costs, 2)
#     plan.balance = round(plan.current_total_budget - plan.total_spent, 2)
#     plan.timestamp = datetime.now(timezone.utc)

#     logger.info(f"Final plan state for {reference_id}: Total Budget={plan.current_total_budget}, "
#                 f"Sum of Estimates={round(sum(c.estimated_amount for c in plan.budget_breakdown), 2)}, "
#                 f"Total Spent={plan.total_spent}, Balance={plan.balance}")

#     # Save the updated plan to the database
#     document_to_db = plan.model_dump() 
#     try:
#         db[BUDGET_PLANS_COLLECTION].update_one({"reference_id": reference_id}, {"$set": document_to_db})
#         logger.info(f"Batch budget adjustments processed and saved for reference_id: {reference_id}")
#     except Exception as e:
#         logger.error(f"Error saving batch adjusted budget plan for reference_id: {reference_id} to DB: {e}", exc_info=True)
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save batch adjusted budget plan.")

#     return plan 



# # app/services/budget_service.py
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

# # NEW: Mapping from budget category names to vendor collection names
# # This is crucial for synchronizing deletions between budget breakdown and selected vendors.
# BUDGET_CATEGORY_TO_VENDOR_COLLECTION_MAP = {
#     "Venue": "venues",
#     "Caterer": "catering",
#     "Photography": "photographers",
#     "Makeup": "makeups",
#     "DJ": "djs",
#     "Decor": "decors",
#     "Mehendi": "mehendi",
#     "Bridal Wear": "bridal_wear",
#     "Wedding Invitations": "weddingInvitations",
#     "Honeymoon": "honeymoon",
#     "Car": "car",
#     "Astrology": "astro", # Assuming "Astrology" is the budget category for "astro" collection
#     "Jewellery": "jewellery",
#     "Wedding Planner": "wedding_planner",
#     # Add any other budget categories and their corresponding vendor collection names here.
#     # If a budget category has no corresponding vendor collection (e.g., "Contingency"),
#     # it doesn't need to be in this map.
# }


# def process_batch_adjustments_fixed_total(
#     reference_id: str,
#     request_data: BatchAdjustEstimatesFixedTotalRequest
# ) -> BudgetPlanDBSchema:
#     """
#     Process batch adjustments including updates, additions, and deletions.
#     Ensures total estimates always equal total budget (100% allocation).
    
#     Deletion Behavior:
#     1. Single category deleted: Amount redistributed to remaining categories, total budget unchanged
#     2. Multiple categories deleted: Combined amounts redistributed to remaining categories
#     3. ALL categories deleted: 
#        - Budget breakdown becomes empty []
#        - Total budget maintained (original or user-specified)
#        - Total spent becomes 0 (no categories = no spending)
#        - Balance becomes equal to total budget (everything available)
#        - Any actual costs from deleted categories are effectively "refunded"
    
#     Adjustment Behavior:
#     1. When category estimates are explicitly changed, remaining untouched categories
#        are adjusted proportionally to ensure total estimates = total budget
#     2. Maintains 100% budget allocation at all times
    
#     Example - All categories deleted:
#     Before: Total=30000, Venue=15000(paid 12000), Caterer=10000(paid 5000), DJ=5000(unpaid)
#     After:  Total=30000, Categories=[], Spent=0, Balance=30000
#     Result: User gets full budget back as available balance
#     """
#     logger.info(f"Processing batch adjustments for plan_id: {reference_id}")

#     # Fetch the existing budget plan using 'reference_id'
#     plan_dict = db[BUDGET_PLANS_COLLECTION].find_one({"reference_id": reference_id})
#     if not plan_dict:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Budget plan with reference_id '{reference_id}' not found.")

#     try:
#         # Validate and load the existing plan
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
#         # Keep the original total budget - this is key for proper redistribution
#         effective_total_budget = plan.current_total_budget
#         logger.info(f"Using existing total budget: {effective_total_budget}")

#     # --- Step 1: Initialize working_categories_map with current plan's categories ---
#     working_categories_map: Dict[str, BudgetCategoryBreakdown] = {
#         cat.category_name: cat.model_copy() for cat in plan.budget_breakdown
#     }
    
#     # --- Step 2: Process Deletions and handle actual costs ---
#     categories_to_be_deleted_names = {
#         del_item.category_name for del_item in request_data.deletions 
#         if del_item.category_name.lower() not in ["string", "example", "placeholder", "test"] # Skip placeholders
#     }
    
#     # Track deleted amounts and actual costs for redistribution
#     deleted_estimated_amount = 0.0
#     deleted_actual_cost = 0.0
    
#     for cat_name in categories_to_be_deleted_names:
#         if cat_name in working_categories_map:
#             deleted_category = working_categories_map[cat_name]
#             deleted_estimated_amount += deleted_category.estimated_amount
            
#             # Handle actual cost of deleted category
#             if deleted_category.actual_cost is not None and deleted_category.actual_cost > 0:
#                 deleted_actual_cost += deleted_category.actual_cost
#                 logger.info(f"Deleted category '{cat_name}' had actual cost of {deleted_category.actual_cost}")
            
#             logger.info(f"Deleting category '{cat_name}' with estimated amount {deleted_category.estimated_amount}")
#             del working_categories_map[cat_name]
#         else:
#             logger.warning(f"Category '{cat_name}' requested for deletion not found in current plan estimates.")

#     # --- UPDATED LOGIC: Step 2.5: Remove selected vendors for deleted categories ---
#     if categories_to_be_deleted_names:
#         original_selected_vendors_count = len(plan.selected_vendors)
        
#         # Determine which vendor collection names correspond to the budget categories being deleted
#         vendor_collections_to_delete_from_selected = set()
#         for budget_cat_name in categories_to_be_deleted_names:
#             vendor_collection_name = BUDGET_CATEGORY_TO_VENDOR_COLLECTION_MAP.get(budget_cat_name)
#             if vendor_collection_name:
#                 vendor_collections_to_delete_from_selected.add(vendor_collection_name)
#             else:
#                 logger.warning(f"No vendor collection mapping found for budget category '{budget_cat_name}'. Selected vendors for this category will not be automatically deleted.")

#         if vendor_collections_to_delete_from_selected:
#             # Filter out selected vendors whose category_name is in the determined set
#             plan.selected_vendors = [
#                 vendor for vendor in plan.selected_vendors
#                 if vendor.category_name not in vendor_collections_to_delete_from_selected
#             ]
#             deleted_selected_vendors_count = original_selected_vendors_count - len(plan.selected_vendors)
#             if deleted_selected_vendors_count > 0:
#                 logger.info(f"Removed {deleted_selected_vendors_count} selected vendor(s) associated with deleted budget categories: {vendor_collections_to_delete_from_selected}.")
#             else:
#                 logger.info(f"No selected vendors found for the deleted budget categories: {vendor_collections_to_delete_from_selected}.")
#         else:
#             logger.info("No corresponding vendor collections found for the deleted budget categories. No selected vendors removed.")
#     # --- END UPDATED LOGIC ---

#     # --- Step 3: Process Adjustments (Updates and Additions) ---
#     categories_explicitly_adjusted_or_added = set()
    
#     if request_data.adjustments:
#         for adj_item in request_data.adjustments:
#             if adj_item.category_name.lower() in ["string", "example", "placeholder", "test"]:
#                 logger.info(f"Skipping placeholder adjustment category name: '{adj_item.category_name}'")
#                 continue
            
#             # Get actual_cost and payment_status with proper attribute access
#             actual_cost = getattr(adj_item, 'actual_cost', None)
#             payment_status = getattr(adj_item, 'payment_status', None)
            
#             # Determine if this is just an actual_cost/payment_status update
#             # If new_estimate is 0 AND we have actual_cost or payment_status, treat as cost-only update
#             is_cost_only_update = (
#                 adj_item.new_estimate == 0 and 
#                 (actual_cost is not None or payment_status is not None)
#             )
            
#             # Skip if no meaningful change (truly empty adjustment)
#             if adj_item.new_estimate == 0 and actual_cost is None and payment_status is None:
#                 logger.info(f"Skipping adjustment for '{adj_item.category_name}' as no meaningful change.")
#                 continue

#             # Estimates cannot be negative
#             if adj_item.new_estimate < 0:
#                 raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Estimate for category '{adj_item.category_name}' cannot be negative.")
            
#             # Actual cost cannot be negative if provided
#             if actual_cost is not None and actual_cost < 0:
#                  raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Actual cost for category '{adj_item.category_name}' cannot be negative.")

#             adj_new_estimate = round(adj_item.new_estimate, 2) if not is_cost_only_update else None
#             adj_actual_cost = round(actual_cost, 2) if actual_cost is not None else None

#             if adj_item.category_name not in categories_to_be_deleted_names:
#                 if adj_item.category_name in working_categories_map: # Update existing category
#                     cat_obj = working_categories_map[adj_item.category_name]
                    
#                     if is_cost_only_update:
#                         # Only update actual_cost and payment_status, keep existing estimate
#                         logger.info(f"Updating only actual_cost/payment_status for '{adj_item.category_name}'. "
#                                    f"Estimate remains: {cat_obj.estimated_amount}")
#                         # Don't add to explicitly adjusted categories since estimate wasn't changed
#                     else:
#                         # Update the estimate
#                         logger.info(f"Updating category '{adj_item.category_name}' estimate from {cat_obj.estimated_amount} to {adj_new_estimate}.")
#                         cat_obj.estimated_amount = adj_new_estimate
#                         categories_explicitly_adjusted_or_added.add(adj_item.category_name)
                    
#                     # Always update actual_cost and payment_status if provided
#                     if hasattr(cat_obj, 'actual_cost'):
#                         cat_obj.actual_cost = adj_actual_cost
#                     if hasattr(cat_obj, 'payment_status'):
#                         cat_obj.payment_status = payment_status
                        
#                 else: # Add new category
#                     if is_cost_only_update:
#                         # For new categories, if it's cost-only update, set estimate to 0
#                         estimate_for_new = 0.0
#                         logger.info(f"Adding new category '{adj_item.category_name}' with cost-only update. Estimate set to 0.")
#                     else:
#                         estimate_for_new = adj_new_estimate
#                         logger.info(f"Adding new category '{adj_item.category_name}' with estimate {estimate_for_new}.")
#                         categories_explicitly_adjusted_or_added.add(adj_item.category_name)
                    
#                     new_cat_data = {
#                         "category_name": adj_item.category_name,
#                         "estimated_amount": estimate_for_new,
#                         "percentage": 0.0  # Will be recalculated later
#                     }
                    
#                     # Add optional fields if they exist in the model
#                     if adj_actual_cost is not None:
#                         new_cat_data["actual_cost"] = adj_actual_cost
#                     if payment_status is not None:
#                         new_cat_data["payment_status"] = payment_status
                    
#                     new_cat_obj = BudgetCategoryBreakdown(**new_cat_data)
#                     working_categories_map[adj_item.category_name] = new_cat_obj
                
#             else:
#                 logger.warning(f"Skipping adjustment for '{adj_item.category_name}' as it was marked for deletion.")

#     # --- Step 4: Handle Redistribution and 100% Allocation ---
#     if not working_categories_map: # All categories were deleted
#         logger.info("All categories removed. Budget breakdown will be empty.")
#         plan.budget_breakdown = []
        
#         # Set the total budget
#         plan.current_total_budget = effective_total_budget
        
#         # When all categories are deleted, total_spent should be 0 (no categories = no spending)
#         # But we need to account for any actual costs that were previously recorded
#         if deleted_actual_cost > 0:
#             logger.info(f"All categories deleted had combined actual costs of {deleted_actual_cost}. "
#                        f"Setting total_spent to 0 and adding deleted costs to balance.")
        
#         plan.total_spent = 0.0  # No categories = no spending
#         plan.balance = plan.current_total_budget  # All budget becomes available balance
        
#         logger.info(f"All categories deleted result: "
#                    f"Total Budget={plan.current_total_budget}, "
#                    f"Total Spent=0, Balance={plan.balance}, "
#                    f"Deleted Actual Costs={deleted_actual_cost}")
#     else:
#         # Set the total budget
#         plan.current_total_budget = effective_total_budget
        
#         # **KEY FIX: Ensure 100% allocation by adjusting untouched categories**
#         # Calculate sum of explicitly set/added categories
#         sum_of_explicitly_set_or_added = sum(
#             working_categories_map[name].estimated_amount
#             for name in categories_explicitly_adjusted_or_added
#             if name in working_categories_map
#         )
        
#         # Get untouched categories (those not explicitly adjusted)
#         untouched_categories = {
#             cat_name: cat_obj for cat_name, cat_obj in working_categories_map.items()
#             if cat_name not in categories_explicitly_adjusted_or_added
#         }
        
#         # Calculate remaining budget for untouched categories
#         budget_for_untouched = round(effective_total_budget - sum_of_explicitly_set_or_added, 2)
        
#         if untouched_categories:
#             if budget_for_untouched <= 0:
#                 # No budget left for untouched categories, set them to 0
#                 logger.warning(f"No budget remaining for untouched categories. Setting them to 0.")
#                 for cat_name in untouched_categories.keys():
#                     working_categories_map[cat_name].estimated_amount = 0.0
#             else:
#                 # Get current total of untouched categories for proportional distribution
#                 current_untouched_total = sum(cat.estimated_amount for cat in untouched_categories.values())
                
#                 if current_untouched_total > 0:
#                     # Proportional redistribution to maintain relative proportions
#                     logger.info(f"Redistributing remaining budget ({budget_for_untouched}) proportionally among untouched categories")
#                     for cat_name, cat_obj in untouched_categories.items():
#                         proportion = cat_obj.estimated_amount / current_untouched_total
#                         new_amount = round(budget_for_untouched * proportion, 2)
#                         logger.info(f"Adjusting '{cat_name}' from {cat_obj.estimated_amount} to {new_amount}")
#                         cat_obj.estimated_amount = new_amount
#                 else:
#                     # Equal distribution among untouched categories
#                     logger.info(f"Equal distribution of remaining budget ({budget_for_untouched}) among untouched categories")
#                     amount_per_category = round(budget_for_untouched / len(untouched_categories), 2)
#                     for cat_name, cat_obj in untouched_categories.items():
#                         logger.info(f"Setting '{cat_name}' to {amount_per_category}")
#                         cat_obj.estimated_amount = amount_per_category
#         else:
#             # All categories were explicitly set - check if they sum to total budget
#             if abs(sum_of_explicitly_set_or_added - effective_total_budget) > 0.01:  # Allow small rounding differences
#                 logger.warning(f"All categories explicitly set but sum ({sum_of_explicitly_set_or_added}) != total budget ({effective_total_budget})")

#         # Reconstruct the final budget_breakdown list, preserving original order
#         final_breakdown_list: List[BudgetCategoryBreakdown] = []
#         original_order_names = [cat.category_name for cat in plan.budget_breakdown]

#         # Add categories that were in the original plan and still exist
#         for cat_name in original_order_names:
#             if cat_name in working_categories_map:
#                 final_breakdown_list.append(working_categories_map[cat_name])
        
#         # Add new categories (those that were added in this request)
#         for cat_name, cat_obj in working_categories_map.items():
#             if cat_name not in original_order_names and cat_name not in categories_to_be_deleted_names:
#                 final_breakdown_list.append(cat_obj)
        
#         plan.budget_breakdown = final_breakdown_list

#         # Adjust total_spent by removing deleted actual costs
#         if deleted_actual_cost > 0:
#             plan.total_spent = max(0.0, plan.total_spent - deleted_actual_cost)
#             logger.info(f"Adjusted total_spent by removing deleted actual costs: -{deleted_actual_cost}")

#     # --- Step 5: Recalculate Percentages, Total Spent, and Balance ---
#     # Recalculate percentages to ensure they add up to 100%
#     if plan.current_total_budget > 0:
#         for item in plan.budget_breakdown:
#             item.percentage = round((item.estimated_amount / plan.current_total_budget) * 100, 2)
#     else:
#         for item in plan.budget_breakdown:
#             item.percentage = 0.0

#     # Recalculate total_spent based on remaining categories
#     remaining_actual_costs = 0.0
#     for cat in plan.budget_breakdown:
#         if hasattr(cat, 'actual_cost') and cat.actual_cost is not None:
#             remaining_actual_costs += cat.actual_cost
    
#     plan.total_spent = round(remaining_actual_costs, 2)
#     plan.balance = round(plan.current_total_budget - plan.total_spent, 2)
#     plan.timestamp = datetime.now(timezone.utc)

#     # Validation: Ensure estimates sum to total budget (within rounding tolerance)
#     total_estimates = sum(c.estimated_amount for c in plan.budget_breakdown)
#     if plan.budget_breakdown and abs(total_estimates - plan.current_total_budget) > 0.01:
#         logger.warning(f"Total estimates ({total_estimates}) do not equal total budget ({plan.current_total_budget})")
    
#     logger.info(f"Final plan state for {reference_id}: Total Budget={plan.current_total_budget}, "
#                 f"Sum of Estimates={round(total_estimates, 2)}, "
#                 f"Total Spent={plan.total_spent}, Balance={plan.balance}")

#     # Save the updated plan to the database
#     document_to_db = plan.model_dump() 
#     try:
#         db[BUDGET_PLANS_COLLECTION].update_one({"reference_id": reference_id}, {"$set": document_to_db})
#         logger.info(f"Batch budget adjustments processed and saved for reference_id: {reference_id}")
#     except Exception as e:
#         logger.error(f"Error saving batch adjusted budget plan for reference_id: {reference_id} to DB: {e}", exc_info=True)
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save batch adjusted budget plan.")

#     return plan





# app/services/budget_service.py
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

# Configuration for handling budget mismatches when all categories are explicitly set
AUTO_ADJUST_ALL_CATEGORIES_WHEN_MISMATCH = False  # Set to True to enable auto-adjustment (respects user's exact values)

# NEW: Mapping from budget category names to vendor collection names
# This is crucial for synchronizing deletions between budget breakdown and selected vendors.
BUDGET_CATEGORY_TO_VENDOR_COLLECTION_MAP = {
    "Venue": "venues",
    "Caterer": "catering",
    "Photography": "photographers",
    "Makeup": "makeups",
    "DJ": "djs",
    "Decor": "decors",
    "Mehendi": "mehendi",
    "Bridal Wear": "bridal_wear",
    "Wedding Invitations": "weddingInvitations",
    "Honeymoon": "honeymoon",
    "Car": "car",
    "Astrology": "astro", # Assuming "Astrology" is the budget category for "astro" collection
    "Jewellery": "jewellery",
    "Wedding Planner": "wedding_planner",
    # Add any other budget categories and their corresponding vendor collection names here.
    # If a budget category has no corresponding vendor collection (e.g., "Contingency"),
    # it doesn't need to be in this map.
}


def process_batch_adjustments_fixed_total(
    reference_id: str,
    request_data: BatchAdjustEstimatesFixedTotalRequest
) -> BudgetPlanDBSchema:
    """
    Process batch adjustments including updates, additions, and deletions.
    Ensures total estimates always equal total budget (100% allocation).
    
    Deletion Behavior:
    1. Single category deleted: Amount redistributed to remaining categories, total budget unchanged
    2. Multiple categories deleted: Combined amounts redistributed to remaining categories
    3. ALL categories deleted: 
       - Budget breakdown becomes empty []
       - Total budget maintained (original or user-specified)
       - Total spent becomes 0 (no categories = no spending)
       - Balance becomes equal to total budget (everything available)
       - Any actual costs from deleted categories are effectively "refunded"
    
    Adjustment Behavior:
    1. When category estimates are explicitly changed, remaining untouched categories
       are adjusted proportionally to ensure total estimates = total budget
    2. Maintains 100% budget allocation at all times
    
    Example - All categories deleted:
    Before: Total=30000, Venue=15000(paid 12000), Caterer=10000(paid 5000), DJ=5000(unpaid)
    After:  Total=30000, Categories=[], Spent=0, Balance=30000
    Result: User gets full budget back as available balance
    """
    logger.info(f"Processing batch adjustments for plan_id: {reference_id}")

    # Fetch the existing budget plan using 'reference_id'
    plan_dict = db[BUDGET_PLANS_COLLECTION].find_one({"reference_id": reference_id})
    if not plan_dict:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Budget plan with reference_id '{reference_id}' not found.")

    try:
        # Validate and load the existing plan
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
        # Keep the original total budget - this is key for proper redistribution
        effective_total_budget = plan.current_total_budget
        logger.info(f"Using existing total budget: {effective_total_budget}")

    # --- Step 1: Initialize working_categories_map with current plan's categories ---
    working_categories_map: Dict[str, BudgetCategoryBreakdown] = {
        cat.category_name: cat.model_copy() for cat in plan.budget_breakdown
    }
    
    # --- Step 2: Process Deletions and handle actual costs ---
    categories_to_be_deleted_names = {
        del_item.category_name for del_item in request_data.deletions 
        if del_item.category_name.lower() not in ["string", "example", "placeholder", "test"] # Skip placeholders
    }
    
    # Track deleted amounts and actual costs for redistribution
    deleted_estimated_amount = 0.0
    deleted_actual_cost = 0.0
    
    for cat_name in categories_to_be_deleted_names:
        if cat_name in working_categories_map:
            deleted_category = working_categories_map[cat_name]
            deleted_estimated_amount += deleted_category.estimated_amount
            
            # Handle actual cost of deleted category
            if deleted_category.actual_cost is not None and deleted_category.actual_cost > 0:
                deleted_actual_cost += deleted_category.actual_cost
                logger.info(f"Deleted category '{cat_name}' had actual cost of {deleted_category.actual_cost}")
            
            logger.info(f"Deleting category '{cat_name}' with estimated amount {deleted_category.estimated_amount}")
            del working_categories_map[cat_name]
        else:
            logger.warning(f"Category '{cat_name}' requested for deletion not found in current plan estimates.")

    # --- UPDATED LOGIC: Step 2.5: Remove selected vendors for deleted categories ---
    if categories_to_be_deleted_names:
        original_selected_vendors_count = len(plan.selected_vendors)
        
        # Determine which vendor collection names correspond to the budget categories being deleted
        vendor_collections_to_delete_from_selected = set()
        for budget_cat_name in categories_to_be_deleted_names:
            vendor_collection_name = BUDGET_CATEGORY_TO_VENDOR_COLLECTION_MAP.get(budget_cat_name)
            if vendor_collection_name:
                vendor_collections_to_delete_from_selected.add(vendor_collection_name)
            else:
                logger.warning(f"No vendor collection mapping found for budget category '{budget_cat_name}'. Selected vendors for this category will not be automatically deleted.")

        if vendor_collections_to_delete_from_selected:
            # Filter out selected vendors whose category_name is in the determined set
            plan.selected_vendors = [
                vendor for vendor in plan.selected_vendors
                if vendor.category_name not in vendor_collections_to_delete_from_selected
            ]
            deleted_selected_vendors_count = original_selected_vendors_count - len(plan.selected_vendors)
            if deleted_selected_vendors_count > 0:
                logger.info(f"Removed {deleted_selected_vendors_count} selected vendor(s) associated with deleted budget categories: {vendor_collections_to_delete_from_selected}.")
            else:
                logger.info(f"No selected vendors found for the deleted budget categories: {vendor_collections_to_delete_from_selected}.")
        else:
            logger.info("No corresponding vendor collections found for the deleted budget categories. No selected vendors removed.")
    # --- END UPDATED LOGIC ---

    # --- Step 3: Process Adjustments (Updates and Additions) ---
    categories_explicitly_adjusted_or_added = set()
    
    if request_data.adjustments:
        for adj_item in request_data.adjustments:
            if adj_item.category_name.lower() in ["string", "example", "placeholder", "test"]:
                logger.info(f"Skipping placeholder adjustment category name: '{adj_item.category_name}'")
                continue
            
            # Get actual_cost and payment_status with proper attribute access
            actual_cost = getattr(adj_item, 'actual_cost', None)
            payment_status = getattr(adj_item, 'payment_status', None)
            
            # Determine if this is just an actual_cost/payment_status update
            # If new_estimate is 0 AND we have actual_cost or payment_status, treat as cost-only update
            is_cost_only_update = (
                adj_item.new_estimate == 0 and 
                (actual_cost is not None or payment_status is not None)
            )
            
            # Skip if no meaningful change (truly empty adjustment)
            if adj_item.new_estimate == 0 and actual_cost is None and payment_status is None:
                logger.info(f"Skipping adjustment for '{adj_item.category_name}' as no meaningful change.")
                continue

            # Estimates cannot be negative
            if adj_item.new_estimate < 0:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Estimate for category '{adj_item.category_name}' cannot be negative.")
            
            # Actual cost cannot be negative if provided
            if actual_cost is not None and actual_cost < 0:
                 raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Actual cost for category '{adj_item.category_name}' cannot be negative.")

            adj_new_estimate = round(adj_item.new_estimate, 2) if not is_cost_only_update else None
            adj_actual_cost = round(actual_cost, 2) if actual_cost is not None else None

            if adj_item.category_name not in categories_to_be_deleted_names:
                if adj_item.category_name in working_categories_map: # Update existing category
                    cat_obj = working_categories_map[adj_item.category_name]
                    
                    if is_cost_only_update:
                        # Only update actual_cost and payment_status, keep existing estimate
                        logger.info(f"Updating only actual_cost/payment_status for '{adj_item.category_name}'. "
                                   f"Estimate remains: {cat_obj.estimated_amount}")
                        # Don't add to explicitly adjusted categories since estimate wasn't changed
                    else:
                        # Update the estimate
                        logger.info(f"Updating category '{adj_item.category_name}' estimate from {cat_obj.estimated_amount} to {adj_new_estimate}.")
                        cat_obj.estimated_amount = adj_new_estimate
                        categories_explicitly_adjusted_or_added.add(adj_item.category_name)
                    
                    # Always update actual_cost and payment_status if provided
                    if hasattr(cat_obj, 'actual_cost'):
                        cat_obj.actual_cost = adj_actual_cost
                    if hasattr(cat_obj, 'payment_status'):
                        cat_obj.payment_status = payment_status
                        
                else: # Add new category
                    if is_cost_only_update:
                        # For new categories, if it's cost-only update, set estimate to 0
                        estimate_for_new = 0.0
                        logger.info(f"Adding new category '{adj_item.category_name}' with cost-only update. Estimate set to 0.")
                    else:
                        estimate_for_new = adj_new_estimate
                        logger.info(f"Adding new category '{adj_item.category_name}' with estimate {estimate_for_new}.")
                        categories_explicitly_adjusted_or_added.add(adj_item.category_name)
                    
                    new_cat_data = {
                        "category_name": adj_item.category_name,
                        "estimated_amount": estimate_for_new,
                        "percentage": 0.0  # Will be recalculated later
                    }
                    
                    # Add optional fields if they exist in the model
                    if adj_actual_cost is not None:
                        new_cat_data["actual_cost"] = adj_actual_cost
                    if payment_status is not None:
                        new_cat_data["payment_status"] = payment_status
                    
                    new_cat_obj = BudgetCategoryBreakdown(**new_cat_data)
                    working_categories_map[adj_item.category_name] = new_cat_obj
                
            else:
                logger.warning(f"Skipping adjustment for '{adj_item.category_name}' as it was marked for deletion.")

    # --- Step 4: Handle Redistribution and 100% Allocation ---
    if not working_categories_map: # All categories were deleted
        logger.info("All categories removed. Budget breakdown will be empty.")
        plan.budget_breakdown = []
        
        # Set the total budget
        plan.current_total_budget = effective_total_budget
        
        # When all categories are deleted, total_spent should be 0 (no categories = no spending)
        # But we need to account for any actual costs that were previously recorded
        if deleted_actual_cost > 0:
            logger.info(f"All categories deleted had combined actual costs of {deleted_actual_cost}. "
                       f"Setting total_spent to 0 and adding deleted costs to balance.")
        
        plan.total_spent = 0.0  # No categories = no spending
        plan.balance = plan.current_total_budget  # All budget becomes available balance
        
        logger.info(f"All categories deleted result: "
                   f"Total Budget={plan.current_total_budget}, "
                   f"Total Spent=0, Balance={plan.balance}, "
                   f"Deleted Actual Costs={deleted_actual_cost}")
    else:
        # Set the total budget
        plan.current_total_budget = effective_total_budget
        
        # **KEY FIX: Ensure 100% allocation by adjusting untouched categories**
        # Calculate sum of explicitly set/added categories
        sum_of_explicitly_set_or_added = sum(
            working_categories_map[name].estimated_amount
            for name in categories_explicitly_adjusted_or_added
            if name in working_categories_map
        )
        
        # Get untouched categories (those not explicitly adjusted)
        untouched_categories = {
            cat_name: cat_obj for cat_name, cat_obj in working_categories_map.items()
            if cat_name not in categories_explicitly_adjusted_or_added
        }
        
        # Calculate remaining budget for untouched categories
        budget_for_untouched = round(effective_total_budget - sum_of_explicitly_set_or_added, 2)
        
        if untouched_categories:
            if budget_for_untouched <= 0:
                # No budget left for untouched categories, set them to 0
                logger.warning(f"No budget remaining for untouched categories. Setting them to 0.")
                for cat_name in untouched_categories.keys():
                    working_categories_map[cat_name].estimated_amount = 0.0
            else:
                # Get current total of untouched categories for proportional distribution
                current_untouched_total = sum(cat.estimated_amount for cat in untouched_categories.values())
                
                if current_untouched_total > 0:
                    # Proportional redistribution to maintain relative proportions
                    logger.info(f"Redistributing remaining budget ({budget_for_untouched}) proportionally among untouched categories")
                    for cat_name, cat_obj in untouched_categories.items():
                        proportion = cat_obj.estimated_amount / current_untouched_total
                        new_amount = round(budget_for_untouched * proportion, 2)
                        logger.info(f"Adjusting '{cat_name}' from {cat_obj.estimated_amount} to {new_amount}")
                        cat_obj.estimated_amount = new_amount
                else:
                    # Equal distribution among untouched categories
                    logger.info(f"Equal distribution of remaining budget ({budget_for_untouched}) among untouched categories")
                    amount_per_category = round(budget_for_untouched / len(untouched_categories), 2)
                    for cat_name, cat_obj in untouched_categories.items():
                        logger.info(f"Setting '{cat_name}' to {amount_per_category}")
                        cat_obj.estimated_amount = amount_per_category
        else:
            # All categories were explicitly set - handle budget mismatch
            budget_difference = effective_total_budget - sum_of_explicitly_set_or_added
            
            if abs(budget_difference) > 0.01:  # Allow small rounding differences
                logger.warning(f"All categories explicitly set but sum ({sum_of_explicitly_set_or_added}) != total budget ({effective_total_budget}). Difference: {budget_difference}")
                
                if AUTO_ADJUST_ALL_CATEGORIES_WHEN_MISMATCH:
                    # OPTION 1: Proportional adjustment to match total budget
                    if sum_of_explicitly_set_or_added > 0:
                        scaling_factor = effective_total_budget / sum_of_explicitly_set_or_added
                        logger.info(f"Applying scaling factor of {scaling_factor} to all explicitly set categories to match total budget")
                        
                        for cat_name in categories_explicitly_adjusted_or_added:
                            if cat_name in working_categories_map:
                                old_amount = working_categories_map[cat_name].estimated_amount
                                new_amount = round(old_amount * scaling_factor, 2)
                                working_categories_map[cat_name].estimated_amount = new_amount
                                logger.info(f"Scaled '{cat_name}' from {old_amount} to {new_amount}")
                else:
                    logger.info("Auto-adjustment disabled. Categories will maintain user-specified values even if they don't sum to total budget.")
                
                # OPTION 2: Alternative - Add/subtract difference to largest category
                # Uncomment this block if you prefer this approach instead of scaling
                """
                # Find the largest category and adjust it
                largest_cat_name = None
                largest_amount = -1
                for cat_name in categories_explicitly_adjusted_or_added:
                    if cat_name in working_categories_map:
                        if working_categories_map[cat_name].estimated_amount > largest_amount:
                            largest_amount = working_categories_map[cat_name].estimated_amount
                            largest_cat_name = cat_name
                
                if largest_cat_name:
                    old_amount = working_categories_map[largest_cat_name].estimated_amount
                    new_amount = max(0, round(old_amount + budget_difference, 2))
                    working_categories_map[largest_cat_name].estimated_amount = new_amount
                    logger.info(f"Adjusted largest category '{largest_cat_name}' from {old_amount} to {new_amount} to match total budget")
                """

        # Reconstruct the final budget_breakdown list, preserving original order
        final_breakdown_list: List[BudgetCategoryBreakdown] = []
        original_order_names = [cat.category_name for cat in plan.budget_breakdown]

        # Add categories that were in the original plan and still exist
        for cat_name in original_order_names:
            if cat_name in working_categories_map:
                final_breakdown_list.append(working_categories_map[cat_name])
        
        # Add new categories (those that were added in this request)
        for cat_name, cat_obj in working_categories_map.items():
            if cat_name not in original_order_names and cat_name not in categories_to_be_deleted_names:
                final_breakdown_list.append(cat_obj)
        
        plan.budget_breakdown = final_breakdown_list

        # Adjust total_spent by removing deleted actual costs
        if deleted_actual_cost > 0:
            plan.total_spent = max(0.0, plan.total_spent - deleted_actual_cost)
            logger.info(f"Adjusted total_spent by removing deleted actual costs: -{deleted_actual_cost}")

    # --- Step 5: Recalculate Percentages, Total Spent, and Balance ---
    # Recalculate percentages to ensure they add up to 100%
    if plan.current_total_budget > 0:
        for item in plan.budget_breakdown:
            item.percentage = round((item.estimated_amount / plan.current_total_budget) * 100, 2)
    else:
        for item in plan.budget_breakdown:
            item.percentage = 0.0

    # Recalculate total_spent based on remaining categories
    remaining_actual_costs = 0.0
    for cat in plan.budget_breakdown:
        if hasattr(cat, 'actual_cost') and cat.actual_cost is not None:
            remaining_actual_costs += cat.actual_cost
    
    plan.total_spent = round(remaining_actual_costs, 2)
    plan.balance = round(plan.current_total_budget - plan.total_spent, 2)
    plan.timestamp = datetime.now(timezone.utc)

    # Validation: Check if estimates sum to total budget (within rounding tolerance)
    total_estimates = sum(c.estimated_amount for c in plan.budget_breakdown)
    if plan.budget_breakdown:
        budget_difference = abs(total_estimates - plan.current_total_budget)
        if budget_difference > 0.01:
            if AUTO_ADJUST_ALL_CATEGORIES_WHEN_MISMATCH:
                logger.warning(f"Total estimates ({total_estimates}) do not equal total budget ({plan.current_total_budget})")
            else:
                logger.info(f"User explicitly set categories. Total estimates ({total_estimates}) vs total budget ({plan.current_total_budget}). Difference: {total_estimates - plan.current_total_budget}")
                # This is expected behavior when respecting user's exact input
    
    logger.info(f"Final plan state for {reference_id}: Total Budget={plan.current_total_budget}, "
                f"Sum of Estimates={round(total_estimates, 2)}, "
                f"Total Spent={plan.total_spent}, Balance={plan.balance}")

    # Save the updated plan to the database
    document_to_db = plan.model_dump() 
    try:
        db[BUDGET_PLANS_COLLECTION].update_one({"reference_id": reference_id}, {"$set": document_to_db})
        logger.info(f"Batch budget adjustments processed and saved for reference_id: {reference_id}")
    except Exception as e:
        logger.error(f"Error saving batch adjusted budget plan for reference_id: {reference_id} to DB: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save batch adjusted budget plan.")

    return plan