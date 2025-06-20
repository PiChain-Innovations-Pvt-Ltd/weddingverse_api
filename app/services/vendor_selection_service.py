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

def normalize_image_url(url: str) -> str:
    """
    Normalize image URLs to use the correct storage domain.
    Replaces 'https://storage.cloud.google.com' with 'https://storage.googleapis.com'
    
    Args:
        url (str): The original image URL
        
    Returns:
        str: The normalized image URL
    """
    if not url or not isinstance(url, str):
        return url
    
    # Replace the incorrect domain with the correct one
    normalized_url = url.replace(
        "https://storage.cloud.google.com",
        "https://storage.googleapis.com"
    )
    
    # Log the replacement if it occurred
    if normalized_url != url:
        logger.info(f"Normalized URL: {url} -> {normalized_url}")
    
    return normalized_url

def normalize_image_urls(image_urls: List[str]) -> List[str]:
    """
    Normalize a list of image URLs.
    
    Args:
        image_urls (List[str]): List of image URLs
        
    Returns:
        List[str]: List of normalized image URLs
    """
    if not image_urls:
        return image_urls
    
    return [normalize_image_url(url) for url in image_urls if url]

def get_category_to_collection_mapping() -> Dict[str, str]:
    """
    Maps category names to their corresponding database collection names.
    
    Returns:
        Dict[str, str]: Mapping of category names to collection names
    """
    return {
        "venue": "venues",
        "venues": "venues",
        "caterer": "catering",
        "catering": "catering",
        "photography": "photographers",
        "photographer": "photographers",
        "photographers": "photographers",
        "bridal_wear": "bridal_wear",
        "car": "car",
        "decor": "decors",
        "decors": "decors",
        "dj": "djs",
        "djs": "djs",
        "honeymoon": "honeymoon",
        "jewellery": "jewellery",
        "makeup": "makeups",
        "makeups": "makeups",
        "mehendi": "mehendi",
        "wedding_planner": "wedding_planner",
        "wedding_invitation": "weddingInvitations",
        "wedding_invitations": "weddingInvitations",
        "invitations": "weddingInvitations"
    }

def get_collection_name_from_category(category_name: str) -> str:
    """
    Gets the database collection name for a given category name.
    
    Args:
        category_name (str): The category name
        
    Returns:
        str: The corresponding collection name
        
    Raises:
        HTTPException: If the category is not supported
    """
    category_mapping = get_category_to_collection_mapping()
    
    # Convert to lowercase for case-insensitive matching
    normalized_category = category_name.lower().strip()
    
    if normalized_category in category_mapping:
        return category_mapping[normalized_category]
    
    # If direct mapping not found, check if it's already a valid collection name
    valid_collections = {
        "bridal_wear", "car", "catering", "decors", "djs", "honeymoon",
        "jewellery", "makeups", "mehendi", "photographers", "venues",
        "wedding_planner", "weddingInvitations"
    }
    
    if normalized_category in valid_collections:
        return normalized_category
    
    # Category not found
    available_categories = list(category_mapping.keys()) + list(valid_collections)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Invalid category '{category_name}'. Available categories: {sorted(set(available_categories))}"
    )

def add_selected_vendor_to_plan(reference_id: str, category_name: str, vendor_name: str) -> BudgetPlanDBSchema:
    """
    Adds or updates a selected vendor to the user's budget plan within a specific category.
    Fetches vendor data from the corresponding collection based on vendor_name and category_name.

    Args:
        reference_id (str): The unique ID of the budget plan.
        category_name (str): The category of the selected vendor (e.g., 'venues', 'photographers').
        vendor_name (str): The name of the vendor to be selected.

    Returns:
        BudgetPlanDBSchema: The updated budget plan document.

    Raises:
        HTTPException: If the budget plan is not found, category is invalid, vendor not found,
                       or if there's a database error.
    """
    logger.info(f"Attempting to add/update selected vendor for reference_id '{reference_id}', "
                f"category '{category_name}', vendor_name '{vendor_name}'")

    # 1. Map category name to collection name and validate
    try:
        collection_name = get_collection_name_from_category(category_name)
        logger.info(f"Mapped category '{category_name}' to collection '{collection_name}'")
    except HTTPException as he:
        logger.warning(f"Invalid category '{category_name}' provided for vendor selection.")
        raise he

    # 2. Validate vendor_name (should not be empty)
    if not vendor_name or not vendor_name.strip():
        logger.warning(f"Empty or invalid vendor_name provided: '{vendor_name}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Vendor name cannot be empty."
        )

    vendor_name = vendor_name.strip()

    # 3. Fetch vendor data from the corresponding collection
    try:
        # Detect field structure for this collection
        field_map = detect_field_structure(collection_name)
        if not field_map:
            logger.error(f"Could not detect field structure for collection '{collection_name}'")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Could not process vendor data from collection '{collection_name}'"
            )

        # Build projection based on detected fields
        projection = {"_id": 1}
        for standard_field, actual_field in field_map.items():
            projection[actual_field] = 1

        # Search for vendor by name using the detected title field
        title_field = field_map.get("title")
        if not title_field:
            logger.error(f"Could not detect title field for collection '{collection_name}'")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Could not identify name field in collection '{collection_name}'"
            )

        # Use case-insensitive regex search for vendor name
        vendor_doc = db[collection_name].find_one(
            {title_field: {"$regex": f"^{vendor_name}$", "$options": "i"}}, 
            projection
        )
        
        if not vendor_doc:
            logger.warning(f"Vendor with name '{vendor_name}' not found in collection '{collection_name}'")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vendor with name '{vendor_name}' not found in category '{category_name}'"
            )

        # Get the vendor_id from the found document
        vendor_id = str(vendor_doc["_id"])

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

        # Extract and normalize image URLs
        vendor_image_urls = []
        if "image_urls" in field_map and field_map["image_urls"] in vendor_doc:
            image_urls = vendor_doc[field_map["image_urls"]]
            if isinstance(image_urls, list):
                # MODIFIED: Normalize URLs and filter out empty ones
                vendor_image_urls = normalize_image_urls([url for url in image_urls if url and str(url).strip()])
            elif isinstance(image_urls, str) and image_urls.strip():
                # MODIFIED: Normalize single URL
                normalized_url = normalize_image_url(image_urls)
                vendor_image_urls = [normalized_url]

        logger.info(f"Extracted vendor data: title='{vendor_title}', city='{vendor_city}', "
                   f"rating={vendor_rating}, image_urls={len(vendor_image_urls)} images")

        # Log a sample of normalized URLs for verification
        if vendor_image_urls:
            logger.info(f"Sample normalized URLs: {vendor_image_urls[:3]}...")  # Show first 3 URLs

    except HTTPException as he:
        # Re-raise HTTP exceptions
        raise he
    except Exception as e:
        logger.error(f"Error fetching vendor data from collection '{collection_name}' for vendor_name '{vendor_name}': {e}", exc_info=True)
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

    # 5. Create the SelectedVendorInfo object with fetched data (URLs already normalized)
    selected_vendor_info = SelectedVendorInfo(
        category_name=category_name,
        title=vendor_title,
        city=vendor_city,
        rating=vendor_rating,
        image_urls=vendor_image_urls if vendor_image_urls else None
    )

    # 6. Add/Update selected_vendors list in the plan
    #    Logic: If the same vendor (by vendor name and category_name) is already selected, update it.
    #    Otherwise, append it. This allows for multiple selections within a category if vendor names differ.
    existing_vendor_index = -1
    for i, sv in enumerate(plan.selected_vendors):
        if (sv.category_name == category_name and 
            sv.title and vendor_title and 
            sv.title.lower().strip() == vendor_title.lower().strip()):
            existing_vendor_index = i
            break

    if existing_vendor_index != -1:
        # Update existing entry
        plan.selected_vendors[existing_vendor_index] = selected_vendor_info
        logger.info(f"Updated existing selected vendor '{vendor_name}' for category '{category_name}'.")
    else:
        # Add new entry
        plan.selected_vendors.append(selected_vendor_info)
        logger.info(f"Added new selected vendor '{vendor_name}' to category '{category_name}'.")

    # 7. Save the updated plan to the database
    try:
        # Use model_dump() for Pydantic v2 to get a plain dict for MongoDB
        db[BUDGET_PLANS_COLLECTION].update_one(
            {"reference_id": reference_id},
            {"$set": plan.model_dump()}
        )
        logger.info(f"Budget plan '{reference_id}' successfully updated with selected vendor '{vendor_name}'.")
    except Exception as e:
        logger.error(f"Error saving updated budget plan for reference_id '{reference_id}' to DB: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Failed to save selected vendor to budget plan."
        )

    return plan