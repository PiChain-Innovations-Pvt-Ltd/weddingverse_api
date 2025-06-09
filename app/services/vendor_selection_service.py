# weddingverse_api15/app/services/vendor_selection_service.py
from typing import List, Dict, Any
from fastapi import HTTPException, status
from bson import ObjectId
from app.models.budget import BudgetPlanDBSchema
from app.models.vendors import SelectedVendorInfo
from app.services.mongo_service import db
from app.utils.logger import logger
from app.services.vendor_discovery_service import get_available_vendor_categories, detect_field_structure, convert_rating_to_float
from app.config import settings

BUDGET_PLANS_COLLECTION = settings.BUDGET_PLANS_COLLECTION 

# BUDGET_PLANS_COLLECTION = "budget_planner"

def add_selected_vendor_to_plan(reference_id: str, category_name: str, vendor_id: str) -> BudgetPlanDBSchema:
    """
    Adds or updates a selected vendor to the user's budget plan within a specific category.
    Fetches vendor data from the corresponding collection based on vendor_id and category_name.

    Args:
        reference_id (str): The unique ID of the budget plan.
        category_name (str): The category of the selected vendor (e.g., 'venues', 'photographers').
        vendor_id (str): The MongoDB ObjectId of the vendor to be selected.

    Returns:
        BudgetPlanDBSchema: The updated budget plan document.

    Raises:
        HTTPException: If the budget plan is not found, category is invalid, vendor not found,
                       or if there's a database error.
    """
    logger.info(f"Attempting to add/update selected vendor for reference_id '{reference_id}', "
                f"category '{category_name}', vendor_id '{vendor_id}'")

    # 1. Validate the category name against dynamically available categories
    available_collections = get_available_vendor_categories()
    if category_name not in available_collections:
        logger.warning(f"Invalid category '{category_name}' provided for vendor selection. Available: {available_collections}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category '{category_name}'. Not a supported vendor category. Available: {available_collections}"
        )

    # 2. Validate vendor_id format (should be a valid MongoDB ObjectId)
    try:
        object_id = ObjectId(vendor_id)
    except Exception as e:
        logger.warning(f"Invalid vendor_id format '{vendor_id}': {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid vendor_id format. Must be a valid MongoDB ObjectId."
        )

    # 3. Fetch vendor data from the corresponding collection
    try:
        # Detect field structure for this collection
        field_map = detect_field_structure(category_name)
        if not field_map:
            logger.error(f"Could not detect field structure for collection '{category_name}'")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Could not process vendor data from collection '{category_name}'"
            )

        # Build projection based on detected fields
        projection = {"_id": 1}
        for standard_field, actual_field in field_map.items():
            projection[actual_field] = 1

        # Fetch vendor document from collection
        vendor_doc = db[category_name].find_one({"_id": object_id}, projection)
        
        if not vendor_doc:
            logger.warning(f"Vendor with ID '{vendor_id}' not found in collection '{category_name}'")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vendor with ID '{vendor_id}' not found in category '{category_name}'"
            )

        # Extract vendor information using field mapping
        vendor_title = None
        vendor_city = None
        vendor_rating = None
        vendor_image_urls = []

        # Extract title
        if "title" in field_map and field_map["title"] in vendor_doc:
            vendor_title = vendor_doc[field_map["title"]]

        # Extract city
        if "city" in field_map and field_map["city"] in vendor_doc:
            vendor_city = vendor_doc[field_map["city"]]

        # Extract and convert rating
        if "rating" in field_map and field_map["rating"] in vendor_doc:
            vendor_rating = convert_rating_to_float(vendor_doc[field_map["rating"]])

        # Extract all image URLs as a list
        vendor_image_urls = []
        if "image_urls" in field_map and field_map["image_urls"] in vendor_doc:
            image_urls = vendor_doc[field_map["image_urls"]]
            if isinstance(image_urls, list):
                vendor_image_urls = [url for url in image_urls if url and str(url).strip()]
            elif isinstance(image_urls, str) and image_urls.strip():
                vendor_image_urls = [image_urls]

        logger.info(f"Extracted vendor data: title='{vendor_title}', city='{vendor_city}', "
                   f"rating={vendor_rating}, image_urls={len(vendor_image_urls)} images")

    except HTTPException as he:
        # Re-raise HTTP exceptions
        raise he
    except Exception as e:
        logger.error(f"Error fetching vendor data from collection '{category_name}' for vendor_id '{vendor_id}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching vendor data from database"
        )

    # 4. Fetch the existing budget plan
    plan_dict = db[BUDGET_PLANS_COLLECTION].find_one({"reference_id": reference_id})
    if not plan_dict:
        logger.warning(f"Budget plan with reference_id '{reference_id}' not found for vendor selection.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Budget plan with reference_id '{reference_id}' not found."
        )

    try:
        plan = BudgetPlanDBSchema.model_validate(plan_dict)
    except Exception as e:
        logger.error(f"Data validation error for existing plan {reference_id} during vendor selection: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Error validating existing budget plan data."
        )

    # 5. Create the SelectedVendorInfo object with fetched data
    selected_vendor_info = SelectedVendorInfo(
        category_name=category_name,
        vendor_id=vendor_id,
        title=vendor_title,
        city=vendor_city,
        rating=vendor_rating,
        image_urls=vendor_image_urls if vendor_image_urls else None
    )

    # 6. Add/Update selected_vendors list in the plan
    #    Logic: If the same vendor (by vendor_id and category_name) is already selected, update it.
    #    Otherwise, append it. This allows for multiple selections within a category if vendor_ids differ.
    existing_vendor_index = -1
    for i, sv in enumerate(plan.selected_vendors):
        if sv.category_name == category_name and sv.vendor_id == vendor_id:
            existing_vendor_index = i
            break

    if existing_vendor_index != -1:
        # Update existing entry
        plan.selected_vendors[existing_vendor_index] = selected_vendor_info
        logger.info(f"Updated existing selected vendor '{vendor_id}' for category '{category_name}'.")
    else:
        # Add new entry
        plan.selected_vendors.append(selected_vendor_info)
        logger.info(f"Added new selected vendor '{vendor_id}' to category '{category_name}'.")

    # 7. Save the updated plan to the database
    try:
        # Use model_dump() for Pydantic v2 to get a plain dict for MongoDB
        db[BUDGET_PLANS_COLLECTION].update_one(
            {"reference_id": reference_id},
            {"$set": plan.model_dump()}
        )
        logger.info(f"Budget plan '{reference_id}' successfully updated with selected vendor '{vendor_id}'.")
    except Exception as e:
        logger.error(f"Error saving updated budget plan for reference_id '{reference_id}' to DB: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Failed to save selected vendor to budget plan."
        )

    return plan
