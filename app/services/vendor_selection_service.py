# # # app/services/vendor_selection_service.py
# # from datetime import datetime, timezone
# # from typing import List, Optional
# # from fastapi import HTTPException, status

# # from app.models.budget import BudgetPlanDBSchema, SelectedVendor, VendorSelectionRequest, VendorRemovalRequest
# # from app.services.mongo_service import db
# # from app.utils.logger import logger

# # BUDGET_PLANS_COLLECTION = "budget_plans"

# # def _get_budget_plan(reference_id: str) -> BudgetPlanDBSchema:
# #     plan_dict = db[BUDGET_PLANS_COLLECTION].find_one({"reference_id": reference_id})
# #     if not plan_dict:
# #         raise HTTPException(
# #             status_code=status.HTTP_404_NOT_FOUND,
# #             detail=f"Budget plan '{reference_id}' not found."
# #         )
# #     try:
# #         return BudgetPlanDBSchema.model_validate(plan_dict)
# #     except Exception as e:
# #         logger.error(f"Validation error for budget plan {reference_id}: {e}")
# #         raise HTTPException(
# #             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# #             detail="Error reading budget plan data."
# #         )

# # def _save_budget_plan(plan: BudgetPlanDBSchema):
# #     try:
# #         # Use model_dump to ensure all fields, including defaults for new ones, are present
# #         document_to_db = plan.model_dump()
# #         # MongoDB's _id is auto-generated and not part of BudgetPlanDBSchema directly
# #         # We query by reference_id
# #         db[BUDGET_PLANS_COLLECTION].update_one(
# #             {"reference_id": plan.reference_id},
# #             {"$set": document_to_db} # document_to_db will not include _id unless it was part of plan_dict
# #         )
# #     except Exception as e:
# #         logger.error(f"Error saving budget plan {plan.reference_id}: {e}", exc_info=True)
# #         raise HTTPException(
# #             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# #             detail="Failed to save budget plan."
# #         )

# # def add_selected_vendor(reference_id: str, vendor_request: VendorSelectionRequest) -> BudgetPlanDBSchema:
# #     logger.info(f"Selecting vendor '{vendor_request.title}' for category '{vendor_request.category}' in plan '{reference_id}'")
# #     plan = _get_budget_plan(reference_id)

# #     new_selection = SelectedVendor(
# #         category=vendor_request.category,
# #         vendor_id=vendor_request.vendor_id,
# #         title=vendor_request.title,
# #         rating=vendor_request.rating,
# #         city=vendor_request.city
# #         # image_url=vendor_request.image_url # if added to model
# #     )

# #     # Remove existing selection for this category, if any
# #     plan.selected_vendors = [sv for sv in plan.selected_vendors if sv.category != vendor_request.category]
# #     # Add new selection
# #     plan.selected_vendors.append(new_selection)
# #     plan.timestamp = datetime.now(timezone.utc)
# #     _save_budget_plan(plan)
# #     logger.info(f"Vendor selection updated for plan '{reference_id}'.")
# #     return plan

# # def remove_selected_vendor(reference_id: str, removal_request: VendorRemovalRequest) -> BudgetPlanDBSchema:
# #     logger.info(f"Removing selected vendor for category '{removal_request.category}' in plan '{reference_id}'")
# #     plan = _get_budget_plan(reference_id)

# #     original_selection_count = len(plan.selected_vendors)
# #     plan.selected_vendors = [sv for sv in plan.selected_vendors if sv.category != removal_request.category]

# #     if len(plan.selected_vendors) == original_selection_count:
# #         raise HTTPException(
# #             status_code=status.HTTP_404_NOT_FOUND,
# #             detail=f"No vendor was selected for category '{removal_request.category}' to remove."
# #         )

# #     plan.timestamp = datetime.now(timezone.utc)
# #     _save_budget_plan(plan)
# #     logger.info(f"Vendor selection removed for category '{removal_request.category}' in plan '{reference_id}'.")
# #     return plan

# # def get_selected_vendors(reference_id: str) -> List[SelectedVendor]:
# #     logger.info(f"Fetching all selected vendors for plan '{reference_id}'")
# #     plan = _get_budget_plan(reference_id)
# #     return plan.selected_vendors

# # def get_selected_vendor_for_category(reference_id: str, category_name: str) -> Optional[SelectedVendor]:
# #     logger.info(f"Fetching selected vendor for category '{category_name}' in plan '{reference_id}'")
# #     plan = _get_budget_plan(reference_id)
# #     for sv in plan.selected_vendors:
# #         if sv.category == category_name:
# #             return sv
# #     return None 



# # weddingverse_api15/app/services/vendor_selection_service.py
# from typing import List, Dict, Any
# from fastapi import HTTPException, status
# from app.models.budget import BudgetPlanDBSchema
# from app.models.vendors import SelectedVendorInfo, SelectVendorRequest
# from app.services.mongo_service import db
# from app.utils.logger import logger
# from app.services.vendor_discovery_service import get_available_vendor_categories # Import this for validation

# BUDGET_PLANS_COLLECTION = "budget_plans"

# def add_selected_vendor_to_plan(reference_id: str, selection_data: SelectVendorRequest) -> BudgetPlanDBSchema:
#     """
#     Adds or updates a selected vendor to the user's budget plan.

#     Args:
#         reference_id (str): The unique ID of the budget plan.
#         selection_data (SelectVendorRequest): Details of the vendor to be selected.

#     Returns:
#         BudgetPlanDBSchema: The updated budget plan document.

#     Raises:
#         HTTPException: If the budget plan is not found, or the category is invalid,
#                        or if there's a database error.
#     """
#     logger.info(f"Attempting to add/update selected vendor for reference_id '{reference_id}': "
#                 f"'{selection_data.vendor_title}' ({selection_data.category_name})")

#     # 1. Fetch the existing budget plan
#     plan_dict = db[BUDGET_PLANS_COLLECTION].find_one({"reference_id": reference_id})
#     if not plan_dict:
#         logger.warning(f"Budget plan with reference_id '{reference_id}' not found for vendor selection.")
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Budget plan with reference_id '{reference_id}' not found.")

#     try:
#         plan = BudgetPlanDBSchema.model_validate(plan_dict)
#     except Exception as e:
#         logger.error(f"Data validation error for existing plan {reference_id} during vendor selection: {e}")
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error validating existing budget plan data.")

#     # 2. Validate the category name against dynamically available categories
#     available_collections = get_available_vendor_categories()
#     if selection_data.category_name not in available_collections:
#         logger.warning(f"Invalid category '{selection_data.category_name}' provided for vendor selection. Available: {available_collections}")
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail=f"Invalid category '{selection_data.category_name}'. Not a supported vendor category. Available: {available_collections}"
#         )

#     # 3. Create the SelectedVendorInfo object
#     selected_vendor_info = SelectedVendorInfo(
#         category_name=selection_data.category_name,
#         vendor_id=selection_data.vendor_id,
#         title=selection_data.vendor_title,
#         city=selection_data.city,
#         rating=selection_data.rating,
#         image_url=selection_data.image_url
#     )

#     # 4. Add/Update selected_vendors list in the plan
#     #    Logic: If the same vendor (by vendor_id and category_name) is already selected, update it.
#     #    Otherwise, append it. This allows for multiple selections within a category if vendor_ids differ.
#     existing_vendor_index = -1
#     for i, sv in enumerate(plan.selected_vendors):
#         if sv.category_name == selection_data.category_name and sv.vendor_id == selection_data.vendor_id:
#             existing_vendor_index = i
#             break

#     if existing_vendor_index != -1:
#         # Update existing entry
#         plan.selected_vendors[existing_vendor_index] = selected_vendor_info
#         logger.info(f"Updated existing selected vendor '{selection_data.vendor_id}' for category '{selection_data.category_name}'.")
#     else:
#         # Add new entry
#         plan.selected_vendors.append(selected_vendor_info)
#         logger.info(f"Added new selected vendor '{selection_data.vendor_id}' to category '{selection_data.category_name}'.")

#     # 5. Save the updated plan to the database
#     try:
#         # Use model_dump() for Pydantic v2 to get a plain dict for MongoDB
#         db[BUDGET_PLANS_COLLECTION].update_one(
#             {"reference_id": reference_id},
#             {"$set": plan.model_dump()}
#         )
#         logger.info(f"Budget plan '{reference_id}' successfully updated with selected vendor '{selection_data.vendor_id}'.")
#     except Exception as e:
#         logger.error(f"Error saving updated budget plan for reference_id '{reference_id}' to DB: {e}", exc_info=True)
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save selected vendor to budget plan.")

#     return plan 



# weddingverse_api15/app/services/vendor_selection_service.py
from typing import List, Dict, Any
from fastapi import HTTPException, status
from app.models.budget import BudgetPlanDBSchema
from app.models.vendors import SelectedVendorInfo, SelectVendorRequest
from app.services.mongo_service import db
from app.utils.logger import logger
from app.services.vendor_discovery_service import get_available_vendor_categories # Import this for validation

BUDGET_PLANS_COLLECTION = "budget_plans"

def add_selected_vendor_to_plan(reference_id: str, category_name: str, selection_data: SelectVendorRequest) -> BudgetPlanDBSchema:
    """
    Adds or updates a selected vendor to the user's budget plan within a specific category.

    Args:
        reference_id (str): The unique ID of the budget plan.
        category_name (str): The category of the selected vendor (e.g., 'venues', 'photographers').
        selection_data (SelectVendorRequest): Details of the vendor to be selected.

    Returns:
        BudgetPlanDBSchema: The updated budget plan document.

    Raises:
        HTTPException: If the budget plan is not found, or the category is invalid,
                       or if there's a database error.
    """
    logger.info(f"Attempting to add/update selected vendor for reference_id '{reference_id}', category '{category_name}': "
                f"'{selection_data.vendor_title}'")

    # 1. Fetch the existing budget plan
    plan_dict = db[BUDGET_PLANS_COLLECTION].find_one({"reference_id": reference_id})
    if not plan_dict:
        logger.warning(f"Budget plan with reference_id '{reference_id}' not found for vendor selection.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Budget plan with reference_id '{reference_id}' not found.")

    try:
        plan = BudgetPlanDBSchema.model_validate(plan_dict)
    except Exception as e:
        logger.error(f"Data validation error for existing plan {reference_id} during vendor selection: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error validating existing budget plan data.")

    # 2. Validate the category name against dynamically available categories (using the one from path)
    available_collections = get_available_vendor_categories()
    if category_name not in available_collections: # Use category_name directly from argument
        logger.warning(f"Invalid category '{category_name}' provided for vendor selection. Available: {available_collections}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category '{category_name}'. Not a supported vendor category. Available: {available_collections}"
        )

    # 3. Create the SelectedVendorInfo object
    selected_vendor_info = SelectedVendorInfo(
        category_name=category_name, # Use category_name from argument
        vendor_id=selection_data.vendor_id,
        title=selection_data.vendor_title,
        city=selection_data.city,
        rating=selection_data.rating,
        image_url=selection_data.image_url
    )

    # 4. Add/Update selected_vendors list in the plan
    #    Logic: If the same vendor (by vendor_id and category_name) is already selected, update it.
    #    Otherwise, append it. This allows for multiple selections within a category if vendor_ids differ.
    existing_vendor_index = -1
    for i, sv in enumerate(plan.selected_vendors):
        if sv.category_name == category_name and sv.vendor_id == selection_data.vendor_id: # Use category_name from argument
            existing_vendor_index = i
            break

    if existing_vendor_index != -1:
        # Update existing entry
        plan.selected_vendors[existing_vendor_index] = selected_vendor_info
        logger.info(f"Updated existing selected vendor '{selection_data.vendor_id}' for category '{category_name}'.")
    else:
        # Add new entry
        plan.selected_vendors.append(selected_vendor_info)
        logger.info(f"Added new selected vendor '{selection_data.vendor_id}' to category '{category_name}'.")

    # 5. Save the updated plan to the database
    try:
        # Use model_dump() for Pydantic v2 to get a plain dict for MongoDB
        db[BUDGET_PLANS_COLLECTION].update_one(
            {"reference_id": reference_id},
            {"$set": plan.model_dump()}
        )
        logger.info(f"Budget plan '{reference_id}' successfully updated with selected vendor '{selection_data.vendor_id}'.")
    except Exception as e:
        logger.error(f"Error saving updated budget plan for reference_id '{reference_id}' to DB: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save selected vendor to budget plan.")

    return plan