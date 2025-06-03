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

    # Handle null/None budget values
    if request.total_budget is None or request.total_budget <= 0:
        logger.warning(f"Invalid budget provided: {request.total_budget}. Setting to 0.")
        actual_total_budget_input = 0.0 # Renamed for clarity in this function
    else:
        actual_total_budget_input = request.total_budget

    breakdown_list: List[BudgetCategoryBreakdown] = []
    total_allocated_amount_for_defined_categories = 0.0
    sum_of_defined_percentages = 0.0

    # Only create category breakdown if budget is greater than 0
    if actual_total_budget_input > 0:
        for category, percentage_decimal in INITIAL_CATEGORIES_DEFINED.items():
            current_percentage = percentage_decimal
            if current_percentage > 1.0:
                 logger.warning(f"Correcting percentage for {category} from {current_percentage} to {current_percentage/100.0}")
                 current_percentage = current_percentage / 100.0
            
            sum_of_defined_percentages += current_percentage
            estimated_amount = round(actual_total_budget_input * current_percentage, 2)
            breakdown_list.append(
                BudgetCategoryBreakdown(
                    category_name=category,
                    percentage=round(current_percentage * 100, 2),
                    estimated_amount=estimated_amount,
                    # actual_cost and payment_status are intentionally omitted here.
                    # As Optional fields, they will default to None and thus won't be
                    # present in the JSON output for initial plans.
                )
            )
            total_allocated_amount_for_defined_categories += estimated_amount

        # Validate total percentage to avoid errors if definitions are wrong
        if abs(sum_of_defined_percentages - 1.0) > 0.001 and sum_of_defined_percentages > 1.0:
            logger.error(
                f"Defined category percentages sum to {sum_of_defined_percentages*100:.2f}%, "
                "which is MORE than 100%. Please correct category definitions."
            )
        
        # Allocate remaining budget to "Other Expenses / Unallocated" if positive
        remaining_amount = round(actual_total_budget_input - total_allocated_amount_for_defined_categories, 2)
        remaining_percentage_decimal = 0.0
        if actual_total_budget_input > 0:
            remaining_percentage_decimal = round(remaining_amount / actual_total_budget_input, 4)
        
        if remaining_amount > 0.001:
            breakdown_list.append(
                BudgetCategoryBreakdown(
                    category_name=REMAINING_BUDGET_CATEGORY_NAME,
                    percentage=round(remaining_percentage_decimal * 100, 2),
                    estimated_amount=remaining_amount,
                    # actual_cost and payment_status are intentionally omitted here.
                )
            )
            logger.info(f"{(remaining_percentage_decimal * 100):.2f}% of budget ({remaining_amount}) is unallocated.")
        elif sum_of_defined_percentages < 0.999: # Small negative or close to 0 remaining
             logger.info(f"Budget has a small remaining unallocated portion of {remaining_amount} or is fully allocated by defined categories.")
        else: # sum_of_defined_percentages is 1.0 or more
            logger.info("Budget is fully allocated or defined categories exceed 100%. No 'Other Expenses' category added.")
    else:
        logger.info("Budget is 0 or invalid. No category breakdown will be created.")

    timestamp = datetime.now(timezone.utc)

    # Calculate total_spent (initially 0 for a new plan, derived from actual_cost) and balance
    # Safely sum actual_cost, treating None as 0.0
    total_spent = round(sum(cat.actual_cost or 0.0 for cat in breakdown_list), 2)
    
    # balance = current_total_budget - total_spent
    balance = round(actual_total_budget_input - total_spent, 2)

    logger.info(f"Budget calculation - Initial Total Budget: {actual_total_budget_input}, Initial Total Spent: {total_spent}, Initial Balance: {balance}")

    # This is the full data object we will save to DB and return from this service
    full_budget_plan_data = BudgetPlanDBSchema(
        reference_id=clean_reference_id,
        total_budget_input=actual_total_budget_input,
        wedding_dates_input=request.wedding_dates,
        guest_count_input=request.guest_count,
        location_input=request.location,
        no_of_events_input=request.no_of_events,
        budget_breakdown=breakdown_list,
        timestamp=timestamp,
        current_total_budget=actual_total_budget_input,
        total_spent=total_spent,
        balance=balance
    )

    # Using model_dump()
    document_data_to_set = full_budget_plan_data.model_dump()

    try:
        # Using 'reference_id' for querying, as requested
        result = db[BUDGET_PLANS_COLLECTION].update_one(
            {"reference_id": clean_reference_id},
            {"$set": document_data_to_set},
            upsert=True
        )
        if result.upserted_id:
            logger.info(f"New budget plan created for reference_id: {clean_reference_id}")
        elif result.modified_count > 0:
            logger.info(f"Existing budget plan updated for reference_id: {clean_reference_id}")
        else:
            logger.info(f"Budget plan for reference_id: {clean_reference_id} - no changes made (data might be identical).")
    except Exception as e:
        logger.error(f"Error saving budget plan for reference_id: {clean_reference_id} to DB: {e}", exc_info=True)

    return full_budget_plan_data # Return the full data object