# app/services/budget_service.py
from datetime import datetime, timezone
from typing import List
from app.models.budget import InitialBudgetSetupRequest, BudgetPlanDBSchema, BudgetCategoryBreakdown # Updated import
from app.services.mongo_service import db
from app.utils.logger import logger

BUDGET_PLANS_COLLECTION = "budget_plans"

INITIAL_CATEGORIES_DEFINED = {
    "Venue": 0.25,
    "Caterer": 0.25,
    "Photography": 0.25,
    "Makeup": 0.25
}
REMAINING_BUDGET_CATEGORY_NAME = "Other Expenses / Unallocated"

# The service function now returns the full DB schema object
def create_initial_budget_plan(request: InitialBudgetSetupRequest) -> BudgetPlanDBSchema:
    clean_reference_id = request.reference_id.strip()
    logger.info(f"Processing budget plan for reference_id: {clean_reference_id}, Input Budget: {request.total_budget}")

    actual_total_budget = request.total_budget

    breakdown_list: List[BudgetCategoryBreakdown] = []
    total_allocated_amount_for_defined_categories = 0.0
    sum_of_defined_percentages = 0.0

    for category, percentage_decimal in INITIAL_CATEGORIES_DEFINED.items():
        current_percentage = percentage_decimal
        if current_percentage > 1.0:
             logger.warning(f"Correcting percentage for {category} from {current_percentage} to {current_percentage/100.0}")
             current_percentage = current_percentage / 100.0
        
        sum_of_defined_percentages += current_percentage
        estimated_amount = round(actual_total_budget * current_percentage, 2)
        breakdown_list.append(
            BudgetCategoryBreakdown(
                category_name=category,
                percentage=round(current_percentage * 100, 2),
                estimated_amount=estimated_amount
            )
        )
        total_allocated_amount_for_defined_categories += estimated_amount

    if abs(sum_of_defined_percentages - 1.0) > 0.001 and sum_of_defined_percentages > 1.0:
        logger.error(
            f"Defined category percentages sum to {sum_of_defined_percentages*100:.2f}%, "
            "which is MORE than 100%. Please correct category definitions."
        )

    remaining_amount = round(actual_total_budget - total_allocated_amount_for_defined_categories, 2)
    remaining_percentage_decimal = 0.0
    if actual_total_budget > 0:
        remaining_percentage_decimal = round(remaining_amount / actual_total_budget, 4)
    
    if remaining_amount > 0.001:
        breakdown_list.append(
            BudgetCategoryBreakdown(
                category_name=REMAINING_BUDGET_CATEGORY_NAME,
                percentage=round(remaining_percentage_decimal * 100, 2),
                estimated_amount=remaining_amount
            )
        )
        logger.info(f"{(remaining_percentage_decimal * 100):.2f}% of budget ({remaining_amount}) is unallocated.")
    elif sum_of_defined_percentages < 0.999:
         logger.info(f"Budget has a small remaining unallocated portion of {remaining_amount} or is fully allocated by defined categories.")
    else:
        logger.info("Budget is fully allocated or defined categories exceed 100%. No 'Other Expenses' category added.")

    timestamp = datetime.now(timezone.utc)

    # Calculate spent and balance correctly
    # spent = total of all estimated amounts from budget breakdown
    total_spent = round(sum(cat.estimated_amount for cat in breakdown_list), 2)
    
    # balance = total_budget - spent (should be 0 or close to 0 for initial setup)
    balance = round(actual_total_budget - total_spent, 2)

    # Log the calculations for verification
    logger.info(f"Budget calculation - Total Budget: {actual_total_budget}, Total Spent: {total_spent}, Balance: {balance}")

    # This is the full data object we will save to DB and return from this service
    full_budget_plan_data = BudgetPlanDBSchema(
        reference_id=clean_reference_id,
        total_budget_input=actual_total_budget,
        wedding_dates_input=request.wedding_dates,
        guest_count_input=request.guest_count,
        location_input=request.location,
        no_of_events_input=request.no_of_events,
        budget_breakdown=breakdown_list,
        timestamp=timestamp,
        current_total_budget=actual_total_budget,
        total_spent=total_spent,
        balance=balance
    )

    document_data_to_set = {
        "_id": clean_reference_id,
        "total_budget_input": full_budget_plan_data.total_budget_input,
        "wedding_dates_input": full_budget_plan_data.wedding_dates_input,
        "guest_count_input": full_budget_plan_data.guest_count_input,
        "location_input": full_budget_plan_data.location_input,
        "no_of_events_input": full_budget_plan_data.no_of_events_input,
        "budget_breakdown": [cat.model_dump() for cat in full_budget_plan_data.budget_breakdown],
        "current_total_budget": full_budget_plan_data.current_total_budget,
        "total_spent": full_budget_plan_data.total_spent,
        "balance": full_budget_plan_data.balance,
        "timestamp": full_budget_plan_data.timestamp
    }
    try:
        result = db[BUDGET_PLANS_COLLECTION].update_one(
            {"_id": clean_reference_id},
            {"$set": document_data_to_set},
            upsert=True
        )
        if result.upserted_id:
            logger.info(f"New budget plan created for _id: {clean_reference_id}")
        elif result.modified_count > 0:
            logger.info(f"Existing budget plan updated for _id: {clean_reference_id}")
        else:
            logger.info(f"Budget plan for _id: {clean_reference_id} - no changes made (data might be identical).")
    except Exception as e:
        logger.error(f"Error saving budget plan for _id: {clean_reference_id} to DB: {e}", exc_info=True)

    return full_budget_plan_data # Return the full data object