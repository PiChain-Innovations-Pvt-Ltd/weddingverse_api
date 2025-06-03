import math
from typing import List, Dict, Any, Tuple
from fastapi import HTTPException, status
from pymongo import ASCENDING, DESCENDING

from app.models.budget import BudgetPlanDBSchema
from app.models.vendors import VendorItem, ExploreVendorsResponse
from app.services.mongo_service import db
from app.utils.logger import logger
from app.config import settings

BUDGET_PLANS_COLLECTION = settings.BUDGET_PLANS_COLLECTION
DEFAULT_PAGE_SIZE = 16

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

def get_vendor_id_from_mongo_id(mongo_id: str) -> str:
    """
    Use MongoDB ObjectId directly as vendor ID.
    
    This function simply returns the MongoDB ObjectId as the vendor ID:
    - Direct mapping from MongoDB ObjectId to vendor_id
    - No hashing or transformation needed
    - Maintains direct relationship with database
    
    Args:
        mongo_id (str): MongoDB ObjectId as string
    
    Returns:
        str: MongoDB ObjectId as vendor ID
    
    Example:
        >>> get_vendor_id_from_mongo_id("507f1f77bcf86cd799439011")
        '507f1f77bcf86cd799439011'
    """
    logger.debug(f"Using MongoDB ObjectId '{mongo_id}' directly as vendor_id")
    return mongo_id

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
            # If the string is empty after stripping, treat as None
            if not cleaned_rating:
                return None
            
            # Try to convert to float
            try:
                return float(cleaned_rating)
            except ValueError:
                # Handle cases like "5 stars", "Excellent" if needed, otherwise return None
                # For now, just return None if it's not a direct float convertible string
                return None 
        elif isinstance(rating_value, (int, float)):
            return float(rating_value)
        else:
            logger.warning(f"Unexpected rating format: {rating_value} (type: {type(rating_value)})")
            return None
    except Exception as e: # Catch any other unexpected errors
        logger.warning(f"Failed to process rating '{rating_value}' to float: {e}")
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
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Limit must be between 1 and 200.")

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
    # Ensure all possible variations of the city name are covered for a robust search
    city_variations = []
    # Normalize input location to lower case for comparison
    normalized_location = wedding_location.lower() 
    
    if normalized_location in ["bengaluru", "bangalore"]:
        city_variations = ["Bengaluru", "Bangalore"]
    elif normalized_location in ["mumbai", "bombay"]:
        city_variations = ["Mumbai", "Bombay"]
    elif normalized_location in ["chennai", "madras"]:
        city_variations = ["Chennai", "Madras"]
    elif normalized_location in ["kolkata", "calcutta"]:
        city_variations = ["Kolkata", "Calcutta"]
    elif normalized_location in ["delhi", "new delhi"]: # Delhi is often used interchangeably
        city_variations = ["Delhi", "New Delhi", "NCR"] # NCR often covers Delhi and surrounds
    else:
        # Default to exact match (case-insensitive) for other cities
        city_variations = [wedding_location] 
    
    if len(city_variations) > 1:
        query_filter = {city_field: {"$in": city_variations}}
    else:
        # Use regex for case-insensitive exact match if only one variation
        query_filter = {city_field: {"$regex": f"^{city_variations[0]}$", "$options": "i"}}


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
        # If total_vendors is 0, total_pages is 1, so page 1 is always valid.
        if page > total_pages and total_vendors > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=f"Page {page} does not exist. Total pages: {total_pages}"
            )
        
        # Fetch all matching documents to allow in-memory sorting and slicing
        # This is safe because limit is applied at the Python level after sorting,
        # ensuring consistent results across pages.
        vendor_cursor = db[category_name].find(query_filter, projection)
        all_matching_docs = list(vendor_cursor)
        
        vendors_list: List[VendorItem] = []
        for vendor_doc in all_matching_docs:
            # Step 1: Extract MongoDB ObjectId and use it directly as vendor_id
            mongo_id = str(vendor_doc["_id"])
            vendor_id = get_vendor_id_from_mongo_id(mongo_id)
            
            # Step 2: Remove MongoDB _id from response (since we're using it as vendor_id)
            del vendor_doc["_id"]
            
            # Step 3: Start building normalized document with MongoDB ObjectId as vendor_id
            normalized_doc = {"vendor_id": vendor_id}
            
            # Step 4: Map actual field names to standard names for consistent API response
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
            
            # Step 5: Create VendorItem and add to list
            vendors_list.append(VendorItem.model_validate(normalized_doc))
        
        logger.info(f"Successfully processed {len(vendors_list)} vendors before pagination")

        # --- Stable Sorting for Pagination ---
        # Sort key to ensure consistent ordering, even with identical ratings.
        # 1. `is_none_rating`: Ensures vendors with actual ratings appear before 'Not Available' (None).
        #    False comes before True, so non-None ratings come first.
        # 2. `rating_sort_value`: Sorts by rating itself. For 'desc', ratings are negated.
        #    For 'asc', ratings are positive, and None is effectively treated as 'infinity' (last).
        # 3. `vendor.vendor_id`: This is the crucial tie-breaker. Since vendor_id is the MongoDB ObjectId,
        #    it guarantees a stable and identical sort order every time, even if ratings are the same.
        def custom_sort_key(vendor: VendorItem) -> Tuple[bool, float, str]:
            is_none_rating = vendor.rating is None
            
            # Assign a very low/high value for None ratings based on order for consistent sorting behavior
            if order.lower() == 'desc':
                # For descending, None should appear last, so assign it a value that sorts after actual numbers
                # A smaller (more negative) value ensures it sorts after positive ratings
                rating_value_for_sort = vendor.rating if not is_none_rating else float('-inf') 
            else: # order.lower() == 'asc'
                # For ascending, None should appear last, so assign it a value that sorts after actual numbers
                # A larger (more positive) value ensures it sorts after actual numbers
                rating_value_for_sort = vendor.rating if not is_none_rating else float('inf')

            # Apply order for rating value
            if order.lower() == "desc":
                final_rating_component = -rating_value_for_sort # Negative for descending
            else:
                final_rating_component = rating_value_for_sort # Positive for ascending
            
            return (is_none_rating, final_rating_component, vendor.vendor_id)

        vendors_list.sort(key=custom_sort_key)

        # Apply pagination (slicing)
        start_index = (page - 1) * limit
        end_index = start_index + limit
        paginated_vendors = vendors_list[start_index:end_index]
        
        logger.info(f"Returning page {page} with {len(paginated_vendors)} vendors")

        # --- VERIFICATION STEP (for internal check, not for production runtime typically) ---
        # This part helps you verify uniqueness and non-repetition during development/testing.
        if len(paginated_vendors) > 0:
            vendor_ids_on_page = {v.vendor_id for v in paginated_vendors}
            if len(vendor_ids_on_page) != len(paginated_vendors):
                logger.error(f"DUPLICATE VENDORS DETECTED ON PAGE {page} for category {category_name}! This should not happen with current sorting logic.")
        # --- END VERIFICATION STEP ---

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

def demonstrate_vendor_id_usage() -> Dict[str, Any]:
    """
    Demonstration function showing how vendor ID works with direct MongoDB ObjectId.
    This function shows that vendor_id is now directly the MongoDB ObjectId.
    
    Returns:
        Dict containing examples of vendor ID usage
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
        # Get vendor ID (now directly the MongoDB ObjectId)
        vendor_id = get_vendor_id_from_mongo_id(vendor["objectid"])
        
        examples.append({
            "collection": vendor["collection"],
            "mongodb_objectid": vendor["objectid"],
            "vendor_title": vendor["title"],
            "vendor_id": vendor_id,
            "explanation": f"MongoDB ObjectId '{vendor['objectid']}' is used directly as vendor_id '{vendor_id}'"
        })
    
    return {
        "message": "Vendor IDs are now directly MongoDB ObjectIds",
        "key_points": [
            "vendor_id = MongoDB ObjectId (direct mapping)",
            "No hashing or transformation applied",
            "Direct relationship with database maintained",
            "Simpler implementation and debugging"
        ],
        "examples": examples,
        "benefits": {
            "simplicity": "Direct mapping, no complex transformations",
            "transparency": "Clear relationship between API and database",
            "uniqueness": "MongoDB ObjectIds are guaranteed unique",
            "efficiency": "No additional processing needed"
        }
    }
