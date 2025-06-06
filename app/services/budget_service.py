# app/services/budget_service.py - Fixed to save timestamps as strings

from dateutil import tz
from datetime import datetime
from typing import List
from app.models.budget import InitialBudgetSetupRequest, BudgetPlanDBSchema, BudgetCategoryBreakdown
from app.services.mongo_service import db
from app.utils.logger import logger
from app.config import settings

BUDGET_PLANS_COLLECTION = settings.BUDGET_PLANS_COLLECTION

INITIAL_CATEGORIES_DEFINED = {
    "Venue": 0.25,
    "Caterer": 0.25,
    "Photography": 0.25,
    "Makeup": 0.25
}
REMAINING_BUDGET_CATEGORY_NAME = "Other Expenses / Unallocated"

# Simple IST timestamp utility
def get_ist_timestamp() -> str:
    """Get current timestamp in IST format: YYYY-MM-DD HH:MM:SS"""
    ist = tz.gettz("Asia/Kolkata")
    return datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

def create_initial_budget_plan(request: InitialBudgetSetupRequest) -> BudgetPlanDBSchema:
    clean_reference_id = request.reference_id.strip()
    logger.info(f"Processing budget plan for reference_id: {clean_reference_id}, Input Budget: {request.total_budget}")

    # Handle null/None budget values
    if request.total_budget is None or request.total_budget <= 0:
        logger.warning(f"Invalid budget provided: {request.total_budget}. Setting to 0.")
        actual_total_budget_input = 0.0
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
        elif sum_of_defined_percentages < 0.999:
             logger.info(f"Budget has a small remaining unallocated portion of {remaining_amount} or is fully allocated by defined categories.")
        else:
            logger.info("Budget is fully allocated or defined categories exceed 100%. No 'Other Expenses' category added.")
    else:
        logger.info("Budget is 0 or invalid. No category breakdown will be created.")

    # ✅ Create IST timestamp as string
    timestamp_string = get_ist_timestamp()
    logger.info(f"Creating budget plan with IST timestamp: {timestamp_string}")

    # Calculate total_spent and balance
    total_spent = round(sum(cat.actual_cost or 0.0 for cat in breakdown_list), 2)
    balance = round(actual_total_budget_input - total_spent, 2)

    logger.info(f"Budget calculation - Initial Total Budget: {actual_total_budget_input}, Initial Total Spent: {total_spent}, Initial Balance: {balance}")

    # Create the full data object with string timestamp
    full_budget_plan_data = BudgetPlanDBSchema(
        reference_id=clean_reference_id,
        total_budget_input=actual_total_budget_input,
        wedding_dates_input=request.wedding_dates,
        guest_count_input=request.guest_count,
        location_input=request.location,
        no_of_events_input=request.no_of_events,
        budget_breakdown=breakdown_list,
        timestamp=timestamp_string,  # ✅ String timestamp, not datetime object
        current_total_budget=actual_total_budget_input,
        total_spent=total_spent,
        balance=balance
    )

    # Convert to dict for database storage
    document_data = full_budget_plan_data.model_dump()
    
    # ✅ Ensure timestamp remains a string in the database
    # No additional conversion needed since model_dump() preserves the string
    logger.info(f"Saving to database with timestamp: {document_data['timestamp']} (type: {type(document_data['timestamp'])})")

    try:
        result = db[BUDGET_PLANS_COLLECTION].update_one(
            {"reference_id": clean_reference_id},
            {"$set": document_data},
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

    return full_budget_plan_data