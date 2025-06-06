# app/services/vendor_details_service.py
from typing import Dict, Any
from fastapi import HTTPException, status
from bson import ObjectId

from app.models.vendors import VendorDetails
from app.services.mongo_service import db
from app.utils.logger import logger

# Collections that are NOT vendor collections
EXCLUDED_COLLECTIONS = {
    "budget_planner", "chat_conversations", "conversations", 
    "image_description", "WeddingVerse_Output"
}

def get_available_vendor_categories() -> list[str]:
    """
    Dynamically discover all vendor collections.
    Returns list of collection names that can be used as categories.
    """
    try:
        all_collections = db.list_collection_names()
        vendor_collections = [
            col for col in all_collections 
            if col not in EXCLUDED_COLLECTIONS
        ]
        logger.info(f"Available vendor categories: {vendor_collections}")
        return vendor_collections
    except Exception as e:
        logger.error(f"Error getting collection names: {e}")
        return []

def get_vendor_details_by_id(vendor_id: str, category_name: str) -> VendorDetails:
    """
    Fetch complete vendor information by vendor_id from the specified category collection.
    
    This function:
    1. Takes vendor_id (MongoDB ObjectId) and category_name
    2. Finds the document in MongoDB by _id
    3. Returns ALL fields from the document (no field mapping needed)
    4. Works with any database structure
    
    Args:
        vendor_id (str): The MongoDB ObjectId of the vendor
        category_name (str): The category/collection name where the vendor exists
        
    Returns:
        VendorDetails: Complete vendor information with all available fields
        
    Raises:
        HTTPException: If vendor not found, category invalid, or vendor_id malformed
    """
    logger.info(f"[VENDOR_DETAILS] Fetching details for vendor_id: {vendor_id} from category: {category_name}")
    
    # Validate that the category exists
    available_categories = get_available_vendor_categories()
    if category_name not in available_categories:
        logger.error(f"[VENDOR_DETAILS] Invalid category '{category_name}'. Available: {available_categories}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category '{category_name}'. Available categories: {available_categories}"
        )
    
    try:
        # Validate vendor_id format
        if not ObjectId.is_valid(vendor_id):
            logger.error(f"[VENDOR_DETAILS] Invalid vendor_id format: {vendor_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid vendor_id format: {vendor_id}. Must be a valid MongoDB ObjectId."
            )
        
        # Fetch the complete vendor document from MongoDB
        logger.debug(f"[VENDOR_DETAILS] Querying collection '{category_name}' for _id: {vendor_id}")
        vendor_doc = db[category_name].find_one({"_id": ObjectId(vendor_id)})
        
        if not vendor_doc:
            logger.warning(f"[VENDOR_DETAILS] Vendor not found: {vendor_id} in {category_name}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vendor with ID '{vendor_id}' not found in category '{category_name}'"
            )
        
        logger.info(f"[VENDOR_DETAILS] Successfully found vendor document with {len(vendor_doc)} fields")
        logger.debug(f"[VENDOR_DETAILS] Document fields: {list(vendor_doc.keys())}")
        
        # Remove the MongoDB _id field and convert ObjectId to string
        del vendor_doc["_id"]
        
        # Build vendor details with minimal processing
        vendor_details = {
            "vendor_id": vendor_id,
            "category_name": category_name,
            "title": "Unknown",  # Default values
            "rating": None,
            "city": None,
            "image_urls": None
        }
        
        # Try to extract basic fields if they exist (with flexible field names)
        # Title
        for title_field in ["Title", "title", "Name", "name"]:
            if title_field in vendor_doc:
                vendor_details["title"] = vendor_doc[title_field]
                break
        
        # Rating
        for rating_field in ["Rating", "rating", "Rate"]:
            if rating_field in vendor_doc:
                try:
                    rating_value = vendor_doc[rating_field]
                    if rating_value is not None and str(rating_value).strip():
                        vendor_details["rating"] = float(str(rating_value).strip())
                except (ValueError, TypeError):
                    vendor_details["rating"] = None
                break
        
        # City
        for city_field in ["City", "city"]:
            if city_field in vendor_doc:
                vendor_details["city"] = vendor_doc[city_field]
                break
        
        # Image URLs
        for image_field in ["Image URLs", "Images", "image_urls", "photos"]:
            if image_field in vendor_doc:
                vendor_details["image_urls"] = vendor_doc[image_field]
                break
        
        # Store ALL remaining fields in additional_fields
        # This ensures no data is lost regardless of database structure
        excluded_basic_fields = set()
        for field_lists in [["Title", "title", "Name", "name"], 
                           ["Rating", "rating", "Rate"],
                           ["City", "city"],
                           ["Image URLs", "Images", "image_urls", "photos"]]:
            for field in field_lists:
                if field in vendor_doc:
                    excluded_basic_fields.add(field)
                    break
        
        additional_fields = {}
        for field_name, field_value in vendor_doc.items():
            if field_name not in excluded_basic_fields:
                additional_fields[field_name] = field_value
        
        # Store all additional fields
        if additional_fields:
            vendor_details["additional_fields"] = additional_fields
            logger.debug(f"[VENDOR_DETAILS] Stored {len(additional_fields)} additional fields: {list(additional_fields.keys())}")
        
        logger.info(f"[VENDOR_DETAILS] Successfully processed vendor details")
        return VendorDetails.model_validate(vendor_details)
        
    except HTTPException as he:
        # Re-raise HTTP exceptions without modification
        raise he
    except Exception as e:
        logger.error(f"[VENDOR_DETAILS] Unexpected error fetching vendor {vendor_id} in {category_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching vendor details from database"
        )