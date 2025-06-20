# weddingverse_api-main/app/services/vision_board_vendor_service.py

import httpx
import re
import math
from typing import List, Dict, Any, Tuple
from fastapi import HTTPException, status
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

from app.models.vendors import VendorItem, ExploreVendorsResponse
from app.services.mongo_service import db
from app.utils.logger import logger
from app.config import settings
from app.services.vendor_discovery_service import get_available_vendor_categories, detect_field_structure, convert_rating_to_float

# External API URL (from user's prompt)
# IMPORTANT: Ensure this URL points to your running vision-board API instance.
# If it's running on the same machine, 'http://127.0.0.1:8000' is correct.
EXTERNAL_VISION_BOARD_API_BASE_URL = "http://127.0.0.1:8000/api/v1/vision-board/vision-board"

# Collections that are NOT vendor collections (from vendor_discovery_service)
EXCLUDED_COLLECTIONS = {
    "budget_plans", "chat_conversations", "conversations",
    "image_description", "WeddingVerse_Output", "Vison_Board" # Added Vison_Board
}

# Category to MongoDB Collection Mapping (for internal DB search)
CATEGORY_TO_COLLECTION_MAP = {
    "fashion and attire": "bridal_wear",
    "decor": "decors",
    "venues": "venues", # This will catch "Banglore/Chennai/Hyderabad Venues" if it contains "venues"
}

# Mapping for categories expected by the EXTERNAL API
EXTERNAL_API_CATEGORY_MAPPING = {
    "fashion and attire": "fashion and attire",
    "decor": "decors", # External API expects 'decors' (plural)
    "venues": "venues",
    "bangalore venues": "venues",
    "chennai venues": "venues",
    "hyderabad venues": "venues",
    # Add any other specific mappings for external API if they differ from internal
}

def _get_external_api_category_name(input_category_name: str) -> str:
    """
    Maps the user-provided category name to the category name expected by the external vision board API.
    """
    normalized_input = input_category_name.lower().strip()
    
    external_category = EXTERNAL_API_CATEGORY_MAPPING.get(normalized_input)
    
    if external_category:
        return external_category
    
    # If not found in specific mapping, check if it's one of the direct valid external categories
    valid_external_categories = list(set(EXTERNAL_API_CATEGORY_MAPPING.values())) # Get unique values from the map
    
    # This check is a fallback if the input itself is a valid external category but not in the keys of the map
    if normalized_input in valid_external_categories:
        return normalized_input 
    
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Invalid category for external API: '{input_category_name}'. Must be one of: {', '.join(sorted(valid_external_categories))}."
    )


async def _get_external_vision_board_data(reference_id: str, category_name: str, auth_token: str) -> Dict[str, Any]:
    """
    Fetches vision board data from the external API.
    """
    logger.info(f"Fetching external vision board data for ref_id: {reference_id}, category: {category_name}")
    
    # Use the mapped category name for the external API call
    external_api_category = _get_external_api_category_name(category_name)
    
    url = f"{EXTERNAL_VISION_BOARD_API_BASE_URL}/{reference_id}/category/{external_api_category}"
    logger.info(f"External API URL being called: {url}") # Log the actual URL being called
    
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {auth_token}"
    }

    async with httpx.AsyncClient() as client:
        try:
            # REMOVED HARDCODED RESPONSE - NOW MAKING ACTUAL HTTP REQUEST
            response = await client.get(url, headers=headers)
            response.raise_for_status() # Raise an exception for 4xx/5xx responses
            return response.json() # Return the JSON response from the actual API call
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching external vision board data: {e.response.status_code} - {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"External API error: {e.response.status_code} - {e.response.text}"
            )
        except httpx.RequestError as e:
            logger.error(f"Network error fetching external vision board data: {e}")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Network error connecting to external API: {e}"
            )
        except Exception as e:
            logger.error(f"Unexpected error fetching external vision board data: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred: {e}"
            )

def _map_category_to_collection(input_category_name: str) -> str:
    """
    Maps the input category name to the corresponding MongoDB collection name.
    Handles specific mappings and general category names.
    """
    normalized_input = input_category_name.lower().strip()

    # Check specific mappings first
    if normalized_input in CATEGORY_TO_COLLECTION_MAP:
        return CATEGORY_TO_COLLECTION_MAP[normalized_input]
    
    # Handle "Banglore/Chennai/Hyderabad Venues" type cases
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

def _normalize_image_link(image_link: str) -> str:
    """
    Normalizes image links to match the format stored in the database.
    Replaces 'storage.googleapis.com' with 'storage.cloud.google.com'.
    """
    if "storage.googleapis.com" in image_link:
        return image_link.replace("storage.googleapis.com", "storage.cloud.google.com")
    return image_link

async def get_vision_board_vendors(
    reference_id: str,
    category_name: str,
    auth_token: str,
    page: int = 1,
    limit: int = 16,
    sort_by: str = "Rating",
    order: str = "desc"
) -> ExploreVendorsResponse:
    """
    Retrieves a list of vendors associated with a vision board, filtered by category,
    with pagination and sorting.
    """
    logger.info(f"Getting vision board vendors for ref_id: {reference_id}, category: {category_name}")

    # 1. Fetch data from the external vision board API
    external_data = await _get_external_vision_board_data(reference_id, category_name, auth_token)
    
    vendor_mappings_from_external = []
    external_location = "N/A" # Default location
    
    if external_data:
        if "vendor_mappings" in external_data and isinstance(external_data["vendor_mappings"], list):
            vendor_mappings_from_external = external_data["vendor_mappings"]
        if "location" in external_data and isinstance(external_data["location"], str):
            external_location = external_data["location"]
    
    if not vendor_mappings_from_external:
        logger.warning(f"No 'vendor_mappings' found or it's not a list in external API response for {reference_id}/{category_name}")
        # If no vendor_mappings, return an empty response
        return ExploreVendorsResponse(
            reference_id=reference_id,
            category_name=category_name,
            location=external_location,
            vendors=[],
            page=page,
            limit=limit,
            total_vendors=0,
            total_pages=1
        )

    # 2. Determine the target MongoDB collection
    collection_name = _map_category_to_collection(category_name)
    logger.info(f"Mapped input category '{category_name}' to MongoDB collection: '{collection_name}'")

    # 3. Detect field structure for the target collection
    field_map = detect_field_structure(collection_name)
    if not field_map:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not detect field structure for collection '{collection_name}'."
        )

    # Determine the actual field names for 'City', 'State', 'Image URLs', 'Title', 'Rating'
    city_db_field = field_map.get("city", "City")
    state_db_field = field_map.get("state", "State")
    image_urls_db_field = field_map.get("image_urls", "Image URLs")
    title_db_field = field_map.get("title", "Title")
    rating_db_field = field_map.get("rating", "Rating")

    # Collect all normalized image links from external data
    normalized_image_links_to_find = []
    # This map helps us get the original external image link back from the normalized one found in DB
    original_link_map = {} 
    for mapping in vendor_mappings_from_external:
        original_link = mapping.get("image_link")
        if original_link:
            normalized_link = _normalize_image_link(original_link)
            normalized_image_links_to_find.append(normalized_link)
            original_link_map[normalized_link] = original_link # Store the original link

    if not normalized_image_links_to_find:
        logger.warning("No valid image links found in external vendor mappings.")
        return ExploreVendorsResponse(
            reference_id=reference_id,
            category_name=category_name,
            location=external_location,
            vendors=[],
            page=page,
            limit=limit,
            total_vendors=0,
            total_pages=1
        )

    # Build a single MongoDB query to find all relevant vendors
    # Use $in for image_urls field (which is an array in DB) and regex for city
    query_filter = {
        image_urls_db_field: {"$in": normalized_image_links_to_find},
        city_db_field: {"$regex": f"^{re.escape(external_location)}$", "$options": "i"}
    }
    
    # Define projection to only retrieve necessary fields
    projection = {
        "_id": 1,
        title_db_field: 1,
        rating_db_field: 1,
        image_urls_db_field: 1, # Need this to find the matching original link
        city_db_field: 1,
        state_db_field: 1
    }

    # Determine sort order for MongoDB
    mongo_sort_order = ASCENDING if order.lower() == "asc" else DESCENDING
    
    # Map the sort_by parameter to the actual DB field name
    # Ensure sort_by is one of the fields we project or a default
    valid_sort_fields = {
        "rating": rating_db_field,
        "title": title_db_field,
        "city": city_db_field,
        "state": state_db_field
    }
    sort_db_field = valid_sort_fields.get(sort_by.lower(), rating_db_field) # Default to rating_db_field if invalid sort_by

    # Get total count of matching documents (before pagination)
    total_vendors = db[collection_name].count_documents(query_filter)
    total_pages = math.ceil(total_vendors / limit) if total_vendors > 0 else 1

    # Validate page number against total pages
    if page < 1:
        page = 1
    if page > total_pages and total_vendors > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Page {page} does not exist. Total pages: {total_pages}"
        )

    # Fetch paginated and sorted results directly from MongoDB
    cursor = db[collection_name].find(query_filter, projection) \
               .sort(sort_db_field, mongo_sort_order) \
               .skip((page - 1) * limit) \
               .limit(limit)

    all_vendors: List[VendorItem] = []
    for vendor_doc in cursor:
        vendor_id = str(vendor_doc["_id"])
        title = vendor_doc.get(title_db_field, "Unknown Title")
        rating = convert_rating_to_float(vendor_doc.get(rating_db_field))
        city = vendor_doc.get(city_db_field)
        state = vendor_doc.get(state_db_field)

        # Find the *original* external image link that corresponds to this vendor document.
        # A vendor document might have multiple image URLs, and we need to pick one that
        # was present in the original external_data's vendor_mappings.
        matched_original_image_link = None
        db_image_urls = vendor_doc.get(image_urls_db_field, [])
        if isinstance(db_image_urls, str): # Handle case where it's a single string
            db_image_urls = [db_image_urls]
        
        for db_img_url in db_image_urls:
            normalized_db_img_url = _normalize_image_link(db_img_url)
            if normalized_db_img_url in original_link_map:
                matched_original_image_link = original_link_map[normalized_db_img_url]
                break
        
        image_urls_for_response = [matched_original_image_link] if matched_original_image_link else None

        all_vendors.append(VendorItem(
            vendor_id=vendor_id,
            Title=title,
            rating=rating, # Use lowercase 'rating' for Pydantic model attribute
            **{"Image URLs": image_urls_for_response},
            City=city,
            State=state # Pass the extracted state
        ))

    # The `all_vendors` list is already paginated and sorted by MongoDB.
    # No need for `all_vendors.sort(key=custom_sort_key)` or manual slicing.
    paginated_vendors = all_vendors

    return ExploreVendorsResponse(
        reference_id=reference_id, # Pass reference_id here
        category_name=category_name,
        location=external_location, # Use the location from the external API
        vendors=paginated_vendors,
        page=page,
        limit=limit,
        total_vendors=total_vendors,
        total_pages=total_pages
    )