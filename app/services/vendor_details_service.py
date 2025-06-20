# app/services/vendor_details_service.py
import re
from typing import Dict, Any, List
from fastapi import HTTPException, status
from bson import ObjectId

from app.models.vendors import VendorDetails
from app.services.mongo_service import db
from app.utils.logger import logger
from app.services.vendor_discovery_service import get_available_vendor_categories, detect_field_structure, convert_rating_to_float

# Collections that are NOT vendor collections (re-using from vendor_discovery_service)
EXCLUDED_COLLECTIONS = {
    "budget_plans", "chat_conversations", "conversations", 
    "image_description", "WeddingVerse_Output", "Vison_Board"
}

# MODIFIED: Category to MongoDB Collection Mapping (all keys are now lowercase for consistency)
CATEGORY_TO_COLLECTION_MAP = {
    "fashion and attire": "bridal_wear",
    "decor": "decors",
    "venues": "venues",
    "bangalore venues": "venues",
    "chennai venues": "venues",
    "hyderabad venues": "venues",
}

def _map_category_to_collection(input_category_name: str) -> str:
    """
    Maps the input category name to the corresponding MongoDB collection name.
    Handles specific mappings and general category names.
    """
    normalized_input = input_category_name.lower().strip()

    # Check specific mappings first
    if normalized_input in CATEGORY_TO_COLLECTION_MAP:
        return CATEGORY_TO_COLLECTION_MAP[normalized_input]
    
    # Handle "Banglore/Chennai/Hyderabad Venues" type cases (this block is still relevant for flexibility)
    if "venues" in normalized_input:
        return "venues"

    # Dynamically get available collections and filter out non-vendor ones
    all_collections = db.list_collection_names()
    vendor_collections = [
        col for col in all_collections 
        if col not in EXCLUDED_COLLECTIONS
    ]

    if normalized_input in vendor_collections:
        return normalized_input
    
    logger.warning(f"No direct mapping or valid collection found for category: {input_category_name}")
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported category: '{input_category_name}'. Please provide a valid wedding vendor category."
    )

def _convert_to_googleapis_link(image_link: str) -> str:
    """
    Converts image links from 'storage.cloud.google.com' to 'storage.googleapis.com'.
    """
    if "storage.cloud.google.com" in image_link:
        return image_link.replace("storage.cloud.google.com", "storage.googleapis.com")
    return image_link

def get_vendor_details_by_name(reference_id: str, vendor_name: str, category_name: str) -> VendorDetails:
    """
    Fetch complete vendor information by vendor_name from the specified category collection.
    
    Args:
        reference_id (str): The unique reference ID (not used for direct lookup in this function, but passed for context).
        vendor_name (str): The name of the vendor.
        category_name (str): The category/collection name (e.g., 'venues', 'photographers', etc.)
        
    Returns:
        VendorDetails: Complete vendor information with all available fields.
        
    Raises:
        HTTPException: If vendor not found, category invalid, or other errors.
    """
    logger.info(f"[VENDOR_DETAILS] Fetching details for ref_id: '{reference_id}', vendor_name: '{vendor_name}' from category: '{category_name}'")
    
    # 1. Map category name to collection name and validate
    try:
        collection_name = _map_category_to_collection(category_name)
        logger.info(f"[VENDOR_DETAILS] Mapped category '{category_name}' to collection '{collection_name}'")
    except HTTPException as he:
        logger.warning(f"[VENDOR_DETAILS] Invalid category '{category_name}' provided for vendor details.")
        raise he

    # 2. Detect field structure for this collection
    field_map = detect_field_structure(collection_name)
    if not field_map:
        logger.error(f"[VENDOR_DETAILS] Could not detect field structure for collection '{collection_name}'")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not process vendor data from collection '{collection_name}'"
        )

    # Determine the actual field name for 'Title' in the target collection
    title_db_field = field_map.get("title")
    if not title_db_field:
        logger.error(f"[VENDOR_DETAILS] Could not detect title field for collection '{collection_name}'")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not identify name field in collection '{collection_name}'"
        )

    try:
        # 3. Fetch the complete vendor document from MongoDB by name (case-insensitive exact match)
        query_filter = {title_db_field: {"$regex": f"^{re.escape(vendor_name)}$", "$options": "i"}}
        logger.debug(f"[VENDOR_DETAILS] Querying collection '{collection_name}' with filter: {query_filter}")
        vendor_doc = db[collection_name].find_one(query_filter)
        
        if not vendor_doc:
            logger.warning(f"[VENDOR_DETAILS] Vendor not found: '{vendor_name}' in '{collection_name}'")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vendor with name '{vendor_name}' not found in category '{category_name}'"
            )
        
        logger.info(f"[VENDOR_DETAILS] Successfully found vendor document with {len(vendor_doc)} fields")
        logger.debug(f"[VENDOR_DETAILS] Document fields: {list(vendor_doc.keys())}")
        
        # Remove the MongoDB _id field and convert ObjectId to string for vendor_id
        vendor_id = str(vendor_doc.pop("_id")) # Pop _id and convert to string
        
        # Build vendor details with minimal processing
        vendor_details = {
            "vendor_id": vendor_id,
            "category_name": category_name,
            "title": "Unknown",  # Default values
            "rating": None,
            "city": None,
            "state": None, # Initialize state
            "image_urls": None
        }
        
        # Try to extract basic fields if they exist (with flexible field names)
        # Title
        vendor_details["title"] = vendor_doc.get(title_db_field, "Unknown")
        
        # Rating
        rating_value = vendor_doc.get(field_map.get("rating"))
        vendor_details["rating"] = convert_rating_to_float(rating_value)
        
        # City
        vendor_details["city"] = vendor_doc.get(field_map.get("city"))
        
        # State
        vendor_details["state"] = vendor_doc.get(field_map.get("state"))

        # Image URLs - Convert links
        image_urls_raw = vendor_doc.get(field_map.get("image_urls"))
        if image_urls_raw:
            if isinstance(image_urls_raw, list):
                converted_image_urls = [_convert_to_googleapis_link(url) for url in image_urls_raw if isinstance(url, str)]
                vendor_details["image_urls"] = converted_image_urls if converted_image_urls else None
            elif isinstance(image_urls_raw, str):
                vendor_details["image_urls"] = [_convert_to_googleapis_link(image_urls_raw)]
            else:
                vendor_details["image_urls"] = None
        else:
            vendor_details["image_urls"] = None
        
        # Store ALL remaining fields in additional_fields
        # This ensures no data is lost regardless of database structure
        excluded_basic_fields = {
            title_db_field,
            field_map.get("rating"),
            field_map.get("city"),
            field_map.get("state"),
            field_map.get("image_urls")
        }
        
        additional_fields = {}
        for field_name, field_value in vendor_doc.items():
            if field_name not in excluded_basic_fields:
                additional_fields[field_name] = field_value
        
        # Store all additional fields
        if additional_fields:
            vendor_details["additional_fields"] = additional_fields
            logger.debug(f"[VENDOR_DETAILS] Stored {len(additional_fields)} additional fields: {list(additional_fields.keys())}")
        
        logger.info(f"[VENDOR_DETAILS] Successfully processed vendor details for '{vendor_name}'")
        return VendorDetails.model_validate(vendor_details)
        
    except HTTPException as he:
        # Re-raise HTTP exceptions without modification
        raise he
    except Exception as e:
        logger.error(f"[VENDOR_DETAILS] Unexpected error fetching vendor '{vendor_name}' in '{category_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching vendor details from database"
        )