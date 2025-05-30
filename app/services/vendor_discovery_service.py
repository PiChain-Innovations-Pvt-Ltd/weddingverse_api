# app/services/vendor_discovery_service.py
import math
import hashlib
from typing import List, Dict, Any
from fastapi import HTTPException, status
from pymongo import ASCENDING, DESCENDING

from app.models.budget import BudgetPlanDBSchema
from app.models.vendors import VendorItem, ExploreVendorsResponse
from app.services.mongo_service import db
from app.utils.logger import logger

BUDGET_PLANS_COLLECTION = "budget_plans"
DEFAULT_PAGE_SIZE = 10

# Collections that are NOT vendor collections
EXCLUDED_COLLECTIONS = {
    "budget_plans", "chat_conversations", "conversations", 
    "image_description", "WeddingVerse_Output"
}

# Standard field mapping - what we expect vs what might exist
FIELD_MAPPING = {
    "title": ["Title", "Name", "title", "name"],
    "rating": ["Rating", "rating", "Rate"],
    "image_urls": ["Image URLs", "Images", "image_urls", "photos", "Pictures"],
    "city": ["City", "city"]
}

def generate_vendor_id(mongo_id: str, collection_name: str) -> str:
    """
    Generate a stable, secure vendor ID using hash-based approach.
    
    This function creates a deterministic (not random) vendor ID that:
    - Always produces the same result for the same vendor
    - Hides internal MongoDB ObjectId structure
    - Includes collection context for better organization
    - Provides security through one-way hashing
    
    Args:
        mongo_id (str): MongoDB ObjectId as string
        collection_name (str): Name of the vendor collection (e.g., 'venues', 'photographers')
    
    Returns:
        str: Stable vendor ID (e.g., 'VEN_a1b2c3d4e5f6')
    
    Example:
        >>> generate_vendor_id("507f1f77bcf86cd799439011", "venues")
        'VEN_a1b2c3d4e5f6'
        
        # Same input always produces same output (deterministic):
        >>> generate_vendor_id("507f1f77bcf86cd799439011", "venues")
        'VEN_a1b2c3d4e5f6'  # IDENTICAL result
    """
    # Create stable input string combining collection and MongoDB ObjectId
    stable_input = f"{collection_name}_{mongo_id}"
    
    # Generate MD5 hash (deterministic - same input = same output)
    vendor_hash = hashlib.md5(stable_input.encode()).hexdigest()[:12]
    
    # Create vendor ID with collection prefix for context
    collection_prefix = collection_name[:3].upper()  # e.g., 'venues' -> 'VEN'
    vendor_id = f"{collection_prefix}_{vendor_hash}"
    
    logger.debug(f"Generated vendor_id '{vendor_id}' from ObjectId '{mongo_id}' in collection '{collection_name}'")
    
    return vendor_id

def get_available_vendor_categories() -> List[str]:
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

def detect_field_structure(collection_name: str) -> Dict[str, str]:
    """
    Analyze a collection to detect its field structure.
    Returns mapping of standard field names to actual field names.
    """
    try:
        sample_doc = db[collection_name].find_one()
        if not sample_doc:
            logger.warning(f"No documents found in collection {collection_name}")
            return {}
        
        field_map = {}
        doc_fields = set(sample_doc.keys())
        
        # Find matching fields for each standard field
        for standard_field, possible_names in FIELD_MAPPING.items():
            for possible_name in possible_names:
                if possible_name in doc_fields:
                    field_map[standard_field] = possible_name
                    break
            
            # If no match found, log warning
            if standard_field not in field_map:
                logger.warning(f"No matching field found for '{standard_field}' in collection '{collection_name}'")
        
        logger.info(f"Field mapping for {collection_name}: {field_map}")
        return field_map
        
    except Exception as e:
        logger.error(f"Error detecting field structure for {collection_name}: {e}")
        return {}

def convert_rating_to_float(rating_value):
    """
    Convert rating from string to float, handling various formats.
    Returns None for missing/invalid ratings (will be displayed as "Not Available").
    """
    if rating_value is None or rating_value == '' or str(rating_value).strip() == '':
        return None  # Will be treated as "Not Available"
    
    try:
        if isinstance(rating_value, str):
            cleaned_rating = rating_value.strip()
            if cleaned_rating == '':
                return None
            return float(cleaned_rating)
        elif isinstance(rating_value, (int, float)):
            return float(rating_value)
        else:
            logger.warning(f"Unexpected rating format: {rating_value}")
            return None
    except (ValueError, TypeError) as e:
        logger.warning(f"Failed to convert rating '{rating_value}' to float: {e}")
        return None

def get_vendors_for_category(
    reference_id: str,
    category_name: str,
    sort_by: str,
    order: str,
    page: int = 1,
    limit: int = DEFAULT_PAGE_SIZE
) -> ExploreVendorsResponse:
    logger.info(f"Exploring vendors for category '{category_name}' in plan '{reference_id}' - Page {page}, Limit {limit}")

    # Validate pagination parameters
    if page < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Page number must be 1 or greater.")
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Limit must be between 1 and 100.")

    # 1. Fetch budget plan to get location
    plan_dict = db[BUDGET_PLANS_COLLECTION].find_one({"reference_id": reference_id})
    if not plan_dict:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Budget plan '{reference_id}' not found.")
    
    try:
        budget_plan = BudgetPlanDBSchema.model_validate(plan_dict)
    except Exception as e:
        logger.error(f"Validation error for budget plan {reference_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error reading budget plan data.")

    wedding_location = budget_plan.location_input
    if not wedding_location:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Wedding location not set in the budget plan.")

    # 2. Check if category exists as a collection
    available_categories = get_available_vendor_categories()
    if category_name not in available_categories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Invalid category '{category_name}'. Available categories: {available_categories}"
        )

    # 3. Detect field structure for this collection
    field_map = detect_field_structure(category_name)
    if not field_map.get("city"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Collection '{category_name}' does not have a recognizable location field."
        )

    # 4. Build query filter with location variations
    city_field = field_map["city"]
    city_variations = []
    if wedding_location.lower() in ["bengaluru", "bangalore"]:
        city_variations = ["Bengaluru", "Bangalore"]
    elif wedding_location.lower() in ["mumbai", "bombay"]:
        city_variations = ["Mumbai", "Bombay"]
    else:
        city_variations = [wedding_location]
    
    if len(city_variations) > 1:
        query_filter = {city_field: {"$in": city_variations}}
    else:
        query_filter = {city_field: {"$regex": f"^{wedding_location}$", "$options": "i"}}

    # 5. Build projection based on detected fields
    projection = {"_id": 1}  # Always include _id
    for standard_field, actual_field in field_map.items():
        projection[actual_field] = 1

    logger.info(f"Querying collection '{category_name}' with filter: {query_filter}")

    try:
        total_vendors = db[category_name].count_documents(query_filter)
        logger.info(f"Found {total_vendors} total vendors matching the criteria")
        
        # Calculate total pages
        total_pages = math.ceil(total_vendors / limit) if total_vendors > 0 else 1
        
        # Validate page number doesn't exceed total pages
        if page > total_pages and total_vendors > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=f"Page {page} does not exist. Total pages: {total_pages}"
            )
        
        vendor_cursor = db[category_name].find(query_filter, projection)
        
        vendors_list: List[VendorItem] = []
        for vendor_doc in vendor_cursor:
            # Step 1: Extract MongoDB ObjectId
            mongo_id = str(vendor_doc["_id"])
            
            # Step 2: Generate stable, secure vendor_id using hash-based approach
            vendor_id = generate_vendor_id(mongo_id, category_name)
            
            # Step 3: Remove MongoDB _id from response to hide internal structure
            del vendor_doc["_id"]
            
            # Step 4: Start building normalized document with generated vendor_id
            normalized_doc = {"vendor_id": vendor_id}
            
            # Step 5: Map actual field names to standard names for consistent API response
            for standard_field, actual_field in field_map.items():
                if actual_field in vendor_doc:
                    if standard_field == "title":
                        normalized_doc["Title"] = vendor_doc[actual_field]
                    elif standard_field == "rating":
                        # Convert rating to float, handling various formats
                        normalized_doc["Rating"] = convert_rating_to_float(vendor_doc[actual_field])
                    elif standard_field == "image_urls":
                        normalized_doc["Image URLs"] = vendor_doc[actual_field]
                    elif standard_field == "city":
                        normalized_doc["City"] = vendor_doc[actual_field]
            
            # Step 6: Create VendorItem and add to list
            vendors_list.append(VendorItem.model_validate(normalized_doc))
        
        logger.info(f"Successfully processed {len(vendors_list)} vendors")

        # Sort by ratings - vendors with ratings first, then "Not Available" at the end
        vendors_list.sort(
            key=lambda vendor: (
                vendor.rating is None,  # False for rated vendors, True for None (puts None at end)
                -(vendor.rating if vendor.rating is not None else 0)  # Negative for descending order
            ) if order.lower() == "desc" else (
                vendor.rating is None,  # False for rated vendors, True for None (puts None at end)
                vendor.rating if vendor.rating is not None else 0  # Positive for ascending order
            )
        )

        # Apply pagination
        start_index = (page - 1) * limit
        end_index = start_index + limit
        paginated_vendors = vendors_list[start_index:end_index]
        
        logger.info(f"Returning page {page} with {len(paginated_vendors)} vendors")

    except HTTPException as he:
        # Re-raise HTTP exceptions (like validation errors)
        raise he
    except Exception as e:
        logger.error(f"Error querying vendors for category '{category_name}' in '{wedding_location}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error fetching vendor data.")

    return ExploreVendorsResponse(
        category_name=category_name,
        location=wedding_location,
        vendors=paginated_vendors,
        page=page,
        limit=limit,
        total_vendors=total_vendors,
        total_pages=total_pages
    )

# Helper endpoint to get available categories
def get_supported_categories() -> Dict[str, Any]:
    """Return all supported vendor categories dynamically."""
    categories = get_available_vendor_categories()
    return {
        "supported_categories": categories,
        "total_categories": len(categories)
    }

def demonstrate_vendor_id_generation() -> Dict[str, Any]:
    """
    Demonstration function showing how vendor ID generation works.
    This function shows that hash-based IDs are deterministic, not random.
    
    Returns:
        Dict containing examples of vendor ID generation
    """
    examples = []
    
    # Example vendor data
    test_vendors = [
        {"collection": "venues", "objectid": "507f1f77bcf86cd799439011", "title": "Galaxy Club"},
        {"collection": "venues", "objectid": "507f1f77bcf86cd799439012", "title": "Royal Palace"},
        {"collection": "photographers", "objectid": "507f1f77bcf86cd799439013", "title": "Wedding Shots"},
        {"collection": "caterers", "objectid": "507f1f77bcf86cd799439014", "title": "Tasty Foods"},
    ]
    
    for vendor in test_vendors:
        # Generate vendor ID using our function
        vendor_id = generate_vendor_id(vendor["objectid"], vendor["collection"])
        
        # Show the deterministic nature - same input produces same output
        vendor_id_check = generate_vendor_id(vendor["objectid"], vendor["collection"])
        
        examples.append({
            "collection": vendor["collection"],
            "mongodb_objectid": vendor["objectid"],
            "vendor_title": vendor["title"],
            "generated_vendor_id": vendor_id,
            "consistency_check": vendor_id_check,
            "is_consistent": vendor_id == vendor_id_check,  # Should always be True
            "explanation": f"ObjectId '{vendor['objectid']}' in '{vendor['collection']}' always generates '{vendor_id}'"
        })
    
    return {
        "message": "Hash-based vendor IDs are deterministic (not random)",
        "key_points": [
            "Same MongoDB ObjectId + Collection = Same vendor_id (always)",
            "Different ObjectIds = Different vendor_ids",
            "Hash function is one-way (cannot reverse to get ObjectId)",
            "Provides security by hiding internal database structure"
        ],
        "examples": examples,
        "benefits": {
            "stability": "Same vendor always gets same ID across API calls",
            "security": "Internal MongoDB ObjectId structure is hidden",
            "uniqueness": "Each vendor gets a unique ID",
            "efficiency": "No database storage needed for vendor_id"
        }
    }