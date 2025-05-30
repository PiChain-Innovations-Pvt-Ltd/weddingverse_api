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
    """
    Process batch adjustments including updates, additions, and deletions.
    
    Deletion Behavior:
    1. Single category deleted: Amount redistributed to remaining categories, total budget unchanged
    2. Multiple categories deleted: Combined amounts redistributed to remaining categories
    3. ALL categories deleted: 
       - Budget breakdown becomes empty []
       - Total budget maintained (original or user-specified)
       - Total spent becomes 0 (no categories = no spending)
       - Balance becomes equal to total budget (everything available)
       - Any actual costs from deleted categories are effectively "refunded"
    
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

    # --- Step 4: Handle Redistribution ---
    if not working_categories_map: # All categories were deleted
        logger.info("All categories removed. Budget breakdown will be empty.")
        plan.budget_breakdown = []
        
        # Determine total budget behavior when all categories are deleted
        if user_explicitly_set_total_budget:
            # User set a specific total budget - maintain it
            plan.current_total_budget = effective_total_budget
            logger.info(f"All categories deleted. Maintaining user-specified total budget: {effective_total_budget}")
        else:
            # No explicit total budget set - maintain original budget
            plan.current_total_budget = effective_total_budget  # This is the original budget
            logger.info(f"All categories deleted. Maintaining original total budget: {effective_total_budget}")
        
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
        # If user did NOT explicitly set a new total budget, redistribute deleted amounts
        if not user_explicitly_set_total_budget and deleted_estimated_amount > 0:
            logger.info(f"Redistributing deleted amount of {deleted_estimated_amount} among remaining categories")
            
            # Get untouched categories (those not explicitly adjusted)
            untouched_categories = {
                cat_name: cat_obj for cat_name, cat_obj in working_categories_map.items()
                if cat_name not in categories_explicitly_adjusted_or_added
            }
            
            if untouched_categories:
                # Calculate current total of untouched categories
                current_untouched_total = sum(cat.estimated_amount for cat in untouched_categories.values())
                
                if current_untouched_total > 0:
                    # Proportional redistribution
                    for cat_name, cat_obj in untouched_categories.items():
                        proportion = cat_obj.estimated_amount / current_untouched_total
                        additional_amount = deleted_estimated_amount * proportion
                        cat_obj.estimated_amount = round(cat_obj.estimated_amount + additional_amount, 2)
                        logger.info(f"Redistributed {additional_amount} to '{cat_name}', new amount: {cat_obj.estimated_amount}")
                else:
                    # Equal distribution among untouched categories
                    amount_per_category = deleted_estimated_amount / len(untouched_categories)
                    for cat_name, cat_obj in untouched_categories.items():
                        cat_obj.estimated_amount = round(cat_obj.estimated_amount + amount_per_category, 2)
                        logger.info(f"Equally distributed {amount_per_category} to '{cat_name}', new amount: {cat_obj.estimated_amount}")
            else:
                # No untouched categories, add to balance
                logger.info(f"No untouched categories to redistribute to. Amount {deleted_estimated_amount} will go to balance.")
        
        # Identify categories whose estimates were NOT explicitly set in this request
        untouched_remaining_categories: Dict[str, float] = {}
        for cat_name, cat_obj in working_categories_map.items():
            if cat_name not in categories_explicitly_adjusted_or_added:
                untouched_remaining_categories[cat_name] = cat_obj.estimated_amount

        # Calculate the sum of estimates for categories that were explicitly set/added
        sum_of_explicitly_set_or_added = sum(
            working_categories_map[name].estimated_amount 
            for name in categories_explicitly_adjusted_or_added 
            if name in working_categories_map
        )

        if user_explicitly_set_total_budget:
            # User explicitly set a new total budget
            plan.current_total_budget = effective_total_budget
            logger.info(f"Using user-specified total budget: {effective_total_budget}")
            
            # Determine how much budget is left for untouched categories
            budget_for_untouched = round(effective_total_budget - sum_of_explicitly_set_or_added, 2)
            
            if untouched_remaining_categories:
                sum_of_original_estimates_of_untouched = sum(untouched_remaining_categories.values())

                if budget_for_untouched < 0:
                    logger.warning(f"Budget for untouched categories ({budget_for_untouched}) is negative. Setting them to 0.")
                    for cat_name in untouched_remaining_categories.keys():
                        working_categories_map[cat_name].estimated_amount = 0.0
                elif sum_of_original_estimates_of_untouched > 0:
                    # Proportional redistribution
                    for cat_name, original_est in untouched_remaining_categories.items():
                        proportion = original_est / sum_of_original_estimates_of_untouched
                        new_val = round(budget_for_untouched * proportion, 2)
                        working_categories_map[cat_name].estimated_amount = max(0.0, new_val)
                elif budget_for_untouched > 0:
                    # Equal distribution if original sum was 0
                    amount_per_cat = round(budget_for_untouched / len(untouched_remaining_categories), 2)
                    for cat_name in untouched_remaining_categories.keys():
                        working_categories_map[cat_name].estimated_amount = max(0.0, amount_per_cat)
        else:
            # Keep the original total budget (key change here)
            plan.current_total_budget = effective_total_budget
            logger.info(f"Maintaining original total budget: {effective_total_budget}")

        # Reconstruct the final budget_breakdown list, preserving original order
        final_breakdown_list: List[BudgetCategoryBreakdown] = []
        original_order_names = [cat.category_name for cat in plan.budget_breakdown]

        # Add categories that were in the original plan and still exist
        for cat_name in original_order_names:
            if cat_name in working_categories_map:
                final_breakdown_list.append(working_categories_map[cat_name])
        
        # Add new categories
        for cat_name, cat_obj in working_categories_map.items():
            if cat_name not in original_order_names:
                final_breakdown_list.append(cat_obj)
        
        plan.budget_breakdown = final_breakdown_list

        # Adjust total_spent by removing deleted actual costs
        if deleted_actual_cost > 0:
            plan.total_spent = max(0.0, plan.total_spent - deleted_actual_cost)
            logger.info(f"Adjusted total_spent by removing deleted actual costs: -{deleted_actual_cost}")

    # --- Step 5: Recalculate Percentages, Total Spent, and Balance ---
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

    logger.info(f"Final plan state for {reference_id}: Total Budget={plan.current_total_budget}, "
                f"Sum of Estimates={round(sum(c.estimated_amount for c in plan.budget_breakdown), 2)}, "
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