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
    logger.info(f"Processing batch estimate adjustments for plan_id: {reference_id}")

    plan_dict = db[BUDGET_PLANS_COLLECTION].find_one({"_id": reference_id})
    if not plan_dict:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Budget plan with reference_id '{reference_id}' not found.")

    try:
        plan = BudgetPlanDBSchema.model_validate(plan_dict)
    except Exception as e:
        logger.error(f"Data validation error for existing plan {reference_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error validating existing budget plan data.")

    # Use new budget only if it's greater than 0, otherwise keep existing budget
    if request_data.new_total_budget > 0:
        target_total_budget = request_data.new_total_budget
        budget_was_changed = True
        logger.info(f"Budget updated from {plan.current_total_budget} to {target_total_budget}")
    else:
        target_total_budget = plan.current_total_budget
        budget_was_changed = False
        logger.info(f"Using existing budget: {target_total_budget} (new_total_budget was {request_data.new_total_budget})")

    working_estimates: Dict[str, float] = {cat.category_name: cat.estimated_amount for cat in plan.budget_breakdown}
    
    sum_of_newly_set_estimates = 0.0
    categories_in_batch_adjustment = set()
    new_categories_to_add = []

    for adj_item in request_data.adjustments:
        adj_item.new_estimate = round(adj_item.new_estimate, 2)
        
        # Only process adjustments where new_estimate > 0
        if adj_item.new_estimate <= 0:
            logger.info(f"Skipping category '{adj_item.category_name}' with estimate {adj_item.new_estimate} (must be > 0)")
            continue
        
        # Check if this is a new category (not in existing budget)
        if adj_item.category_name not in working_estimates:
            # This is a new category to be added
            new_categories_to_add.append(adj_item)
            working_estimates[adj_item.category_name] = adj_item.new_estimate
            logger.info(f"Adding new category: '{adj_item.category_name}' with estimate: {adj_item.new_estimate}")
        else:
            # This is an existing category being updated
            working_estimates[adj_item.category_name] = adj_item.new_estimate
            logger.info(f"Updating existing category: '{adj_item.category_name}' to estimate: {adj_item.new_estimate}")
        
        sum_of_newly_set_estimates += adj_item.new_estimate
        categories_in_batch_adjustment.add(adj_item.category_name)

    # Check if any valid adjustments were processed
    if not categories_in_batch_adjustment:
        logger.warning("No valid adjustments found (all estimates were <= 0). No changes made.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="No valid adjustments found. All category estimates must be greater than 0."
        )
    untouched_categories_data: List[Dict[str, any]] = []
    sum_of_original_untouched_estimates = 0.0
    
    # Get untouched categories
    for cat_in_plan in plan.budget_breakdown:
        if cat_in_plan.category_name not in categories_in_batch_adjustment:
            untouched_categories_data.append({"name": cat_in_plan.category_name, "original_estimate": cat_in_plan.estimated_amount})
            sum_of_original_untouched_estimates += cat_in_plan.estimated_amount

    required_sum_for_untouched = round(target_total_budget - sum_of_newly_set_estimates, 2)

    # Handle different scenarios
    if not untouched_categories_data:
        # All categories were specified
        if budget_was_changed:
            logger.info(f"All categories specified with new budget: {target_total_budget}")
        else:
            logger.info(f"All categories adjusted. New total: {sum_of_newly_set_estimates:.2f}, Target budget: {target_total_budget:.2f}")
    elif required_sum_for_untouched < 0:
        # Estimates exceed budget - keep untouched categories at their original values
        logger.warning(f"Estimates ({sum_of_newly_set_estimates:.2f}) exceed target budget ({target_total_budget:.2f}). Maintaining original estimates for untouched categories.")
        # Don't change untouched categories - they keep their original estimates
        # working_estimates already has their original values, so no changes needed
    else:
        # Distribute remaining budget to untouched categories
        if sum_of_original_untouched_estimates > 0:
            # Proportional distribution
            for cat_data in untouched_categories_data:
                proportion = cat_data["original_estimate"] / sum_of_original_untouched_estimates
                new_val = round(required_sum_for_untouched * proportion, 2)
                working_estimates[cat_data["name"]] = max(new_val, 0.0)
        elif required_sum_for_untouched > 0:
            # Equal distribution when original sum was 0
            amount_per_untouched = round(required_sum_for_untouched / len(untouched_categories_data), 2)
            for cat_data in untouched_categories_data:
                working_estimates[cat_data["name"]] = max(amount_per_untouched, 0.0)

    # Reconstruct budget breakdown
    new_breakdown: List[BudgetCategoryBreakdown] = []
    
    # Add existing categories in original order
    for original_cat_in_plan in plan.budget_breakdown:
        cat_name = original_cat_in_plan.category_name
        estimate = working_estimates.get(cat_name, 0.0)
        new_breakdown.append(
            BudgetCategoryBreakdown(category_name=cat_name, estimated_amount=estimate, percentage=0.0)
        )
    
    # Add new categories at the end
    for new_cat in new_categories_to_add:
        new_breakdown.append(
            BudgetCategoryBreakdown(
                category_name=new_cat.category_name, 
                estimated_amount=new_cat.new_estimate, 
                percentage=0.0
            )
        )

    # Update plan with new data
    plan.budget_breakdown = new_breakdown
    plan.current_total_budget = target_total_budget

    # Calculate percentages based on the target budget
    if target_total_budget > 0:
        for cat_item in plan.budget_breakdown:
            cat_item.percentage = round((cat_item.estimated_amount / target_total_budget) * 100, 2)
    else:
        for cat_item in plan.budget_breakdown:
            cat_item.percentage = 0.0

    # Calculate spent and balance
    spent = round(sum(cat.estimated_amount for cat in plan.budget_breakdown), 2)
    balance = round(target_total_budget - spent, 2)

    plan.total_spent = spent
    plan.balance = balance

    # Log results
    if balance < 0:
        logger.warning(f"Budget exceeded by: {abs(balance)}. Total budget: {target_total_budget}, Total spent: {spent}")
    elif balance > 0:
        logger.info(f"Remaining budget: {balance}. Total budget: {target_total_budget}, Total spent: {spent}")
    else:
        logger.info(f"Budget perfectly balanced. Total budget: {target_total_budget}, Total spent: {spent}")

    if new_categories_to_add:
        logger.info(f"Added {len(new_categories_to_add)} new categories: {[cat.category_name for cat in new_categories_to_add]}")

    plan.timestamp = datetime.now(timezone.utc)

    # Save to database
    document_to_db = {
        "_id": reference_id,
        "total_budget_input": plan.total_budget_input,
        "wedding_dates_input": plan.wedding_dates_input,
        "guest_count_input": plan.guest_count_input,
        "location_input": plan.location_input,
        "no_of_events_input": plan.no_of_events_input,
        "budget_breakdown": [cat.model_dump() for cat in plan.budget_breakdown],
        "current_total_budget": plan.current_total_budget,
        "total_spent": plan.total_spent,
        "balance": plan.balance,
        "timestamp": plan.timestamp
    }
    
    try:
        db[BUDGET_PLANS_COLLECTION].update_one({"_id": reference_id}, {"$set": document_to_db})
        logger.info(f"Budget plan processed for _id: {reference_id}")
    except Exception as e:
        logger.error(f"Error saving budget plan for _id: {reference_id} to DB: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save budget plan.")

    return plan