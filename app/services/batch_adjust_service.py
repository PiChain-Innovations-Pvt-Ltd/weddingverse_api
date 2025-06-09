# app/services/batch_adjust_service.py - Fixed timestamp handling

from datetime import datetime, timezone
from dateutil import tz
from typing import List, Dict
from fastapi import HTTPException, status
from app.models.budget import (
    BudgetPlanDBSchema,
    BudgetCategoryBreakdown,
    BatchAdjustEstimatesFixedTotalRequest
)
from app.services.mongo_service import db
from app.utils.logger import logger
from app.config import settings

BUDGET_PLANS_COLLECTION = settings.BUDGET_PLANS_COLLECTION

REMAINING_BUDGET_CATEGORY_NAME = "Other Expenses / Unallocated"

# Configuration for handling budget mismatches when all categories are explicitly set
AUTO_ADJUST_ALL_CATEGORIES_WHEN_MISMATCH = False

# NEW: Mapping from budget category names to vendor collection names
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
    "Astrology": "astro",
    "Jewellery": "jewellery",
    "Wedding Planner": "wedding_planner",
}

# Simple IST timestamp utility
def get_ist_timestamp() -> str:
    """Get current timestamp in IST format: YYYY-MM-DD HH:MM:SS"""
    ist = tz.gettz("Asia/Kolkata")
    return datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

def process_batch_adjustments_fixed_total(
    reference_id: str,
    request_data: BatchAdjustEstimatesFixedTotalRequest
) -> BudgetPlanDBSchema:
    """
    Process batch adjustments including updates, additions, and deletions.
    Enhanced with proper timestamp handling for backward compatibility.
    """
    logger.info(f"Processing batch adjustments for plan_id: {reference_id}")

    # Fetch the existing budget plan using 'reference_id'
    plan_dict = db[BUDGET_PLANS_COLLECTION].find_one({"reference_id": reference_id})
    if not plan_dict:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Budget plan with reference_id '{reference_id}' not found.")

    try:
        # ✅ The model validator will now handle datetime to string conversion
        plan = BudgetPlanDBSchema.model_validate(plan_dict)
        logger.info(f"Successfully validated budget plan for {reference_id} with timestamp: {plan.timestamp}")
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

    # --- Step 1: Initialize working_categories_map with current plan's categories ---
    working_categories_map: Dict[str, BudgetCategoryBreakdown] = {
        cat.category_name: cat.model_copy() for cat in plan.budget_breakdown
    }
    
    # --- Step 2: Process Deletions and handle actual costs ---
    categories_to_be_deleted_names = {
        del_item.category_name for del_item in request_data.deletions 
        if del_item.category_name.lower() not in ["string", "example", "placeholder", "test"]
    }
    
    deleted_estimated_amount = 0.0
    deleted_actual_cost = 0.0
    
    for cat_name in categories_to_be_deleted_names:
        if cat_name in working_categories_map:
            deleted_category = working_categories_map[cat_name]
            deleted_estimated_amount += deleted_category.estimated_amount
            
            if deleted_category.actual_cost is not None and deleted_category.actual_cost > 0:
                deleted_actual_cost += deleted_category.actual_cost
                logger.info(f"Deleted category '{cat_name}' had actual cost of {deleted_category.actual_cost}")
            
            logger.info(f"Deleting category '{cat_name}' with estimated amount {deleted_category.estimated_amount}")
            del working_categories_map[cat_name]
        else:
            logger.warning(f"Category '{cat_name}' requested for deletion not found in current plan estimates.")

    # --- Step 2.5: Remove selected vendors for deleted categories ---
    if categories_to_be_deleted_names:
        original_selected_vendors_count = len(plan.selected_vendors)
        
        vendor_collections_to_delete_from_selected = set()
        for budget_cat_name in categories_to_be_deleted_names:
            vendor_collection_name = BUDGET_CATEGORY_TO_VENDOR_COLLECTION_MAP.get(budget_cat_name)
            if vendor_collection_name:
                vendor_collections_to_delete_from_selected.add(vendor_collection_name)
            else:
                logger.warning(f"No vendor collection mapping found for budget category '{budget_cat_name}'.")

        if vendor_collections_to_delete_from_selected:
            plan.selected_vendors = [
                vendor for vendor in plan.selected_vendors
                if vendor.category_name not in vendor_collections_to_delete_from_selected
            ]
            deleted_selected_vendors_count = original_selected_vendors_count - len(plan.selected_vendors)
            if deleted_selected_vendors_count > 0:
                logger.info(f"Removed {deleted_selected_vendors_count} selected vendor(s) associated with deleted budget categories.")

    # --- Step 3: Process Adjustments (Updates and Additions) ---
    categories_explicitly_adjusted_or_added = set()
    categories_with_new_estimates = set()
    
    currently_user_set_categories = set()
    for cat in plan.budget_breakdown:
        if hasattr(cat, 'is_user_set') and cat.is_user_set:
            currently_user_set_categories.add(cat.category_name)
    
    if request_data.adjustments:
        for adj_item in request_data.adjustments:
            if adj_item.category_name.lower() in ["string", "example", "placeholder", "test"]:
                logger.info(f"Skipping placeholder adjustment category name: '{adj_item.category_name}'")
                continue
            
            actual_cost = getattr(adj_item, 'actual_cost', None)
            payment_status = getattr(adj_item, 'payment_status', None)
            
            is_cost_only_update = (
                adj_item.new_estimate == 0 and 
                (actual_cost is not None or payment_status is not None)
            )
            
            if adj_item.new_estimate == 0 and actual_cost is None and payment_status is None:
                logger.info(f"Skipping adjustment for '{adj_item.category_name}' as no meaningful change.")
                continue

            if adj_item.new_estimate < 0:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Estimate for category '{adj_item.category_name}' cannot be negative.")
            
            if actual_cost is not None and actual_cost < 0:
                 raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Actual cost for category '{adj_item.category_name}' cannot be negative.")

            adj_new_estimate = round(adj_item.new_estimate, 2) if not is_cost_only_update else None
            adj_actual_cost = round(actual_cost, 2) if actual_cost is not None else None

            if adj_item.category_name not in categories_to_be_deleted_names:
                if adj_item.category_name in working_categories_map:
                    cat_obj = working_categories_map[adj_item.category_name]
                    
                    if is_cost_only_update:
                        logger.info(f"Updating only actual_cost/payment_status for '{adj_item.category_name}'. "
                                   f"Estimate remains: {cat_obj.estimated_amount}")
                    else:
                        logger.info(f"Updating category '{adj_item.category_name}' estimate from {cat_obj.estimated_amount} to {adj_new_estimate}.")
                        cat_obj.estimated_amount = adj_new_estimate
                        categories_explicitly_adjusted_or_added.add(adj_item.category_name)
                        categories_with_new_estimates.add(adj_item.category_name)
                        
                        if hasattr(cat_obj, 'is_user_set'):
                            cat_obj.is_user_set = True
                        else:
                            setattr(cat_obj, 'is_user_set', True)
                        logger.info(f"Marked category '{adj_item.category_name}' as user-set for persistent protection")
                    
                    if hasattr(cat_obj, 'actual_cost'):
                        cat_obj.actual_cost = adj_actual_cost
                    if hasattr(cat_obj, 'payment_status'):
                        cat_obj.payment_status = payment_status
                        
                else:
                    if is_cost_only_update:
                        estimate_for_new = 0.0
                        logger.info(f"Adding new category '{adj_item.category_name}' with cost-only update. Estimate set to 0.")
                    else:
                        estimate_for_new = adj_new_estimate
                        logger.info(f"Adding new category '{adj_item.category_name}' with estimate {estimate_for_new}.")
                        categories_explicitly_adjusted_or_added.add(adj_item.category_name)
                        categories_with_new_estimates.add(adj_item.category_name)
                    
                    new_cat_data = {
                        "category_name": adj_item.category_name,
                        "estimated_amount": estimate_for_new,
                        "percentage": 0.0,
                        "is_user_set": True if not is_cost_only_update else False
                    }
                    
                    if adj_actual_cost is not None:
                        new_cat_data["actual_cost"] = adj_actual_cost
                    if payment_status is not None:
                        new_cat_data["payment_status"] = payment_status
                    
                    new_cat_obj = BudgetCategoryBreakdown(**new_cat_data)
                    working_categories_map[adj_item.category_name] = new_cat_obj
                
            else:
                logger.warning(f"Skipping adjustment for '{adj_item.category_name}' as it was marked for deletion.")

    # --- Step 4: Handle Redistribution and 100% Allocation ---
    if not working_categories_map:
        logger.info("All categories removed. Budget breakdown will be empty.")
        plan.budget_breakdown = []
        plan.current_total_budget = effective_total_budget
        
        if deleted_actual_cost > 0:
            logger.info(f"All categories deleted had combined actual costs of {deleted_actual_cost}.")
        
        plan.total_spent = 0.0
        plan.balance = plan.current_total_budget
        
        logger.info(f"All categories deleted result: "
                   f"Total Budget={plan.current_total_budget}, "
                   f"Total Spent=0, Balance={plan.balance}")
    else:
        plan.current_total_budget = effective_total_budget
        
        all_protected_categories = categories_with_new_estimates.union(currently_user_set_categories)
        
        sum_of_protected_categories = sum(
            working_categories_map[name].estimated_amount
            for name in all_protected_categories
            if name in working_categories_map
        )
        
        redistributable_categories = {
            cat_name: cat_obj for cat_name, cat_obj in working_categories_map.items()
            if cat_name not in all_protected_categories
        }
        
        logger.info(f"Protected categories total amount: {sum_of_protected_categories}")
        logger.info(f"Redistributable categories: {list(redistributable_categories.keys())}")
        
        budget_for_redistributable = round(effective_total_budget - sum_of_protected_categories, 2)
        
        if redistributable_categories:
            if budget_for_redistributable <= 0:
                logger.warning(f"No budget remaining for redistributable categories. Setting them to 0.")
                for cat_name in redistributable_categories.keys():
                    working_categories_map[cat_name].estimated_amount = 0.0
            else:
                total_budget_for_redistribution = budget_for_redistributable + deleted_estimated_amount
                logger.info(f"Total budget for redistribution: {total_budget_for_redistribution}")
                
                current_redistributable_total = sum(cat.estimated_amount for cat in redistributable_categories.values())
                
                if current_redistributable_total > 0:
                    logger.info(f"Redistributing budget ({total_budget_for_redistribution}) proportionally among redistributable categories")
                    for cat_name, cat_obj in redistributable_categories.items():
                        proportion = cat_obj.estimated_amount / current_redistributable_total
                        new_amount = round(total_budget_for_redistribution * proportion, 2)
                        logger.info(f"Adjusting '{cat_name}' from {cat_obj.estimated_amount} to {new_amount}")
                        cat_obj.estimated_amount = new_amount
                else:
                    logger.info(f"Equal distribution of budget ({total_budget_for_redistribution}) among redistributable categories")
                    amount_per_category = round(total_budget_for_redistribution / len(redistributable_categories), 2)
                    for cat_name, cat_obj in redistributable_categories.items():
                        logger.info(f"Setting '{cat_name}' to {amount_per_category}")
                        cat_obj.estimated_amount = amount_per_category
        else:
            total_of_all_categories = sum_of_protected_categories
            budget_difference = effective_total_budget - total_of_all_categories
            
            if abs(budget_difference) > 0.01:
                logger.warning(f"All remaining categories have new estimates but sum ({total_of_all_categories}) != total budget ({effective_total_budget}).")

        # Reconstruct the final budget_breakdown list
        final_breakdown_list: List[BudgetCategoryBreakdown] = []
        original_order_names = [cat.category_name for cat in plan.budget_breakdown]

        for cat_name in original_order_names:
            if cat_name in working_categories_map:
                cat_obj = working_categories_map[cat_name]
                if not hasattr(cat_obj, 'is_user_set'):
                    cat_obj.is_user_set = cat_name in categories_with_new_estimates
                final_breakdown_list.append(cat_obj)
        
        for cat_name, cat_obj in working_categories_map.items():
            if cat_name not in original_order_names and cat_name not in categories_to_be_deleted_names:
                if not hasattr(cat_obj, 'is_user_set'):
                    cat_obj.is_user_set = cat_name in categories_with_new_estimates
                final_breakdown_list.append(cat_obj)
        
        plan.budget_breakdown = final_breakdown_list

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

    remaining_actual_costs = 0.0
    for cat in plan.budget_breakdown:
        if hasattr(cat, 'actual_cost') and cat.actual_cost is not None:
            remaining_actual_costs += cat.actual_cost
    
    plan.total_spent = round(remaining_actual_costs, 2)
    plan.balance = round(plan.current_total_budget - plan.total_spent, 2)
    
    # ✅ Update timestamp to IST string format
    plan.timestamp = get_ist_timestamp()
    logger.info(f"Updated plan timestamp to: {plan.timestamp}")

    total_estimates = sum(c.estimated_amount for c in plan.budget_breakdown)
    logger.info(f"Final plan state for {reference_id}: Total Budget={plan.current_total_budget}, "
                f"Sum of Estimates={round(total_estimates, 2)}, "
                f"Total Spent={plan.total_spent}, Balance={plan.balance}")

    # ✅ Save the updated plan with string timestamp
    document_to_db = plan.model_dump() 
    try:
        db[BUDGET_PLANS_COLLECTION].update_one({"reference_id": reference_id}, {"$set": document_to_db})
        logger.info(f"Batch budget adjustments processed and saved for reference_id: {reference_id}")
    except Exception as e:
        logger.error(f"Error saving batch adjusted budget plan for reference_id: {reference_id} to DB: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save batch adjusted budget plan.")

    return plan