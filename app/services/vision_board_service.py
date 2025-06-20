import json
from datetime import datetime
from dateutil import tz
from bson import ObjectId

from fastapi import HTTPException
from pymongo import ASCENDING
from pymongo.errors import OperationFailure
from typing import List

from app.services.mongo_service import db
from app.config import settings, FIELD_MAP
from app.services.genai_service import model
from app.models.vision_board import BoardItem, VisionBoardRequest, VisionBoardResponse, CategoryImagesResponse, ImageVendorMapping,VendorImage,EventImagesResponse  # MODIFIED: Added ImageVendorMapping
from app.utils.logger import logger

IMAGE_INPUT_COLLECTION = settings.image_input_collection
VISION_BOARD_COLLECTION = settings.VISION_BOARD_COLLECTION

def get_matching_boards(user: dict, limit: int = 10) -> list[dict]:
    provided = [k for k in FIELD_MAP if user.get(k)]
    raw_events = user.get("events", []) or []
    events = []
    for e in raw_events:
        if isinstance(e, str) and "," in e:
            events += [s.strip() for s in e.split(",") if s.strip()]
        else:
            events.append(e)
    colors = user.get("colors", []) or []

    # Build conds + keep track of criteria names
    conds = []
    criteria = []

    for key in provided:
        db_field = FIELD_MAP[key]  # e.g. "data.Wedding Preference"
        conds.append({
            "$cond": [{"$eq": [f"${db_field}", user[key]]}, 1, 0]
        })
        criteria.append(("field", key, user[key], db_field))

    for ev in events:
        # Events are in data.Events
        conds.append({
            "$cond": [
                {
                    "$and": [
                        {"$ne": ["$data.Events", None]},
                        {"$isArray": "$data.Events"},
                        {"$in": [ev, "$data.Events"]}
                    ]
                }, 
                1, 
                0
            ]
        })
        criteria.append(("event", ev, None, "data.Events"))

    for clr in colors:
        # Colors are in data.Colors, but we need colorList for comparison
        conds.append({
            "$cond": [
                {
                    "$and": [
                        {"$ne": ["$colorList", None]},
                        {"$isArray": "$colorList"},
                        {"$in": [clr, "$colorList"]}
                    ]
                }, 
                1, 
                0
            ]
        })
        criteria.append(("color", clr, None, "data.Colors"))

    total_fields = len(conds)

    pipeline = [
        {
            "$addFields": {
                "colorList": {
                    "$cond": [
                        {
                            "$and": [
                                {"$ne": ["$data.Colors", None]},
                                {"$isArray": "$data.Colors"}
                            ]
                        },
                        {
                            "$map": {
                                "input": "$data.Colors",
                                "as": "c",
                                "in": "$c.color"
                            }
                        },
                        []  # Default to empty array if Colors is missing or not an array
                    ]
                }
            }
        },
        {
            "$addFields": {
                "matchCount": {"$add": conds} if conds else {"$literal": 0}
            }
        },
        {"$sort": {"matchCount": -1}},
        {
            "$project": {
                "_id": 0,
                "image_link": 1,
                "vendor_id": 1,  # MODIFIED: Include vendor_id in projection
                "data.Events": 1,
                "data.Colors": 1,
                "matchCount": 1,
                "colorList": 1,
                **{db_field: 1 for _, _, _, db_field in criteria}
            }
        }
    ]

    try:
        all_docs = list(db[IMAGE_INPUT_COLLECTION]
                        .aggregate(pipeline, allowDiskUse=True))
    except OperationFailure as e:
        logger.warning("Aggregation failed (%s); falling back.", e)
        cursor = db[IMAGE_INPUT_COLLECTION] \
                   .find({}, {"_id": 0, "image_link": 1, "vendor_id": 1, "data.Colors": 1, "data.Events": 1}) \
                   .sort("_id", ASCENDING).limit(limit)
        fallback_docs = []
        for d in cursor:
            # Ensure data structure exists
            if "data" not in d:
                d["data"] = {}
            if "Colors" not in d["data"]:
                d["data"]["Colors"] = []
            if "Events" not in d["data"]:
                d["data"]["Events"] = []
            d["matchCount"] = 0
            fallback_docs.append(d)
        return fallback_docs

    docs = []
    if total_fields > 0:
        for target in range(total_fields, 0, -1):
            matched = [d for d in all_docs if d["matchCount"] == target]
            if not matched:
                continue

            docs = matched
            first_link = matched[0]["image_link"]
            full_doc = db[IMAGE_INPUT_COLLECTION].find_one(
                {"image_link": first_link},
                {"_id": 0, "data": 1}
            )
            
            # Extract data section
            doc_data = full_doc.get("data", {}) if full_doc else {}

            matched_names = []

            for key in provided:
                data_key = FIELD_MAP[key].split(".", 1)[1]  # Remove "data." prefix
                if doc_data.get(data_key) == user[key]:
                    matched_names.append(f"{key}={user[key]}")

            for ev in events:
                events_list = doc_data.get("Events", [])
                if isinstance(events_list, list) and ev in events_list:
                    matched_names.append(f"event:{ev}")

            for clr in colors:
                colors_data = doc_data.get("Colors", [])
                if isinstance(colors_data, list):
                    color_values = [c.get("color") for c in colors_data if isinstance(c, dict)]
                    if clr in color_values:
                        matched_names.append(f"color:{clr}")

            logger.info(
                f"Matched {len(docs)} docs with {target}/{total_fields} criteria. "
                f"Criteria matched: {matched_names}"
            )
            break

    if not docs:
        logger.warning("No close matches; returning first %d docs.", limit)
        cursor = db[IMAGE_INPUT_COLLECTION] \
                   .find({}, {"_id": 0, "image_link": 1, "vendor_id": 1, "data.Colors": 1, "data.Events": 1}) \
                   .sort("_id", ASCENDING).limit(limit)
        fallback_docs = []
        for d in cursor:
            # Ensure data structure exists
            if "data" not in d:
                d["data"] = {}
            if "Colors" not in d["data"]:
                d["data"]["Colors"] = []
            if "Events" not in d["data"]:
                d["data"]["Events"] = []
            d["matchCount"] = 0
            fallback_docs.append(d)
        docs = fallback_docs

    return docs

def create_vision_board(req: VisionBoardRequest) -> dict:
    try:
        user = req.dict()
        
        # newly added edge case logics
        # Check if all input values are empty
        all_empty = (
            (not user.get("wedding_preference") or user.get("wedding_preference") == "") and
            (not user.get("venue_suits") or user.get("venue_suits") == "") and
            (not user.get("wedding_style") or user.get("wedding_style") == "") and
            (not user.get("wedding_tone") or user.get("wedding_tone") == "") and
            (not user.get("guest_experience") or user.get("guest_experience") == "") and
            (not user.get("events") or len(user.get("events", [])) == 0)
        )
        
        if all_empty:
            logger.warning("Request contains only empty values")
            raise HTTPException(
                status_code=400, 
                detail="No preferences provided. Please specify at least one preference for your vision board."
            )
        
        # Check individual fields
        if not user.get("wedding_preference") or user.get("wedding_preference") == "":
            logger.warning("Missing wedding_preference field")
            raise HTTPException(
                status_code=400,
                detail="Wedding preference is missing. Please specify your wedding preference for your vision board."
            )
            
        if not user.get("venue_suits") or user.get("venue_suits") == "":
            logger.warning("Missing venue_suits field")
            raise HTTPException(
                status_code=400,
                detail="Venue preference is missing. Please specify which venue suits your vision board."
            )
            
        if not user.get("wedding_style") or user.get("wedding_style") == "":
            logger.warning("Missing wedding_style field")
            raise HTTPException(
                status_code=400,
                detail="Wedding style is missing. Please specify your wedding style for your vision board."
            )
            
        if not user.get("wedding_tone") or user.get("wedding_tone") == "":
            logger.warning("Missing wedding_tone field")
            raise HTTPException(
                status_code=400,
                detail="Wedding tone is missing. Please specify your wedding tone for your vision board."
            )
            
        if not user.get("guest_experience") or user.get("guest_experience") == "":
            logger.warning("Missing guest_experience field")
            raise HTTPException(
                status_code=400,
                detail="Guest experience is missing. Please specify your desired guest experience for your vision board."
            )
            
        if not user.get("events") or len(user.get("events", [])) == 0:
            logger.warning("Missing events field")
            raise HTTPException(
                status_code=400,
                detail="Events selection is missing. Please specify at least one event for your vision board."
            )
        
        if not user.get("location") or len(user.get("location", [])) == 0:
            logger.warning("Missing Location field")
            raise HTTPException(
                status_code=400,
                detail="Location selection is missing. Please specify Location for your vision board."
            )
            
        if not user.get("reference_id") or user.get("reference_id") == "":
            logger.warning("Missing reference_id field")
            raise HTTPException(
                status_code=400,
                detail="Reference ID is missing. Please provide a reference ID for your vision board."
            )
            
        # Extract events from the request for the response
        request_events = user.get("events", []) or []
        
        # 1) Fetch matching docs
        docs = get_matching_boards(user, limit=10)

        # MODIFIED: collect image_links and create vendor mappings
        image_links = []
        vendor_mappings = []
        
        for doc in docs:
            image_link = doc.get("image_link")
            vendor_id = doc.get("vendor_id")
            
            if image_link:
                image_links.append(image_link)
                
                # Convert vendor_id to string representation "ObjectId('...')"
                if vendor_id:
                    if isinstance(vendor_id, ObjectId):
                        vendor_id_str = f"ObjectId('{str(vendor_id)}')"
                    else:
                        # If it's already a string, wrap it properly
                        vendor_id_str = f"ObjectId('{vendor_id}')"
                    
                    vendor_mappings.append(ImageVendorMapping(
                        image_link=image_link,
                        vendor_id=vendor_id_str
                    ))

        # FIXED: Extract colors from data.Colors based on exact structure
        color_set = set()
        for doc in docs:
            # Get data section first
            doc_data = doc.get("data", {})
            colors_list = doc_data.get("Colors", [])
            
            if isinstance(colors_list, list):
                for color_item in colors_list:
                    if isinstance(color_item, dict) and "color" in color_item:
                        color_name = color_item["color"]
                        if color_name:  # Make sure it's not empty
                            color_set.add(color_name)
        
        colors = list(color_set)
        logger.info(f"Extracted {len(colors)} colors: {colors}")

        # MODIFIED: instantiate BoardItem with vendor mappings
        board_items = [
            BoardItem(
                image_links=image_links,
                colors=colors,
                vendor_mappings=vendor_mappings
            )
        ]

        # 3) Prepare GenAI prompts
        user_input = json.dumps(user, indent=2)
        system_prompt = (
            "You are a specialized AI assistant for processing wedding vision board inputs. "
            "Your task is to generate precise, evocative titles and concise summaries "
            "that accurately reflect the provided content. Adherence to all specified "
            "constraints and output format is mandatory."
        )

        user_prompt = (
            f"Analyze the following wedding vision board content: {user_input}\n\n"
            "Based on this analysis, provide the following:\n"
            "1. A professional and expressive title, strictly limited to a maximum of two words.\n"
            "2. A single-paragraph summary that clearly and concisely encapsulates the primary theme and aesthetic of the vision board.\n\n"
            "Output the response exclusively as a valid JSON object containing two keys: 'title' and 'summary'."
        )

        # 4) Call the model
        try:
            resp = model.generate_content([system_prompt, user_prompt])
            text = resp.text.strip()
        except Exception:
            logger.error("GenAI call failed", exc_info=True)
            raise HTTPException(status_code=502, detail="Failed to generate vision board summary")

        # 5) Strip code fences and parse JSON
        if text.startswith("```") and text.endswith("```"):
            lines = text.splitlines()
            text = "\n".join([ln for ln in lines if not ln.strip().startswith("```")]).strip()

        try:
            parsed = json.loads(text)
            title = parsed.get("title", "").strip()
            summary = parsed.get("summary", "").strip()
        except json.JSONDecodeError:
            parts = text.split("\n", 1)
            title = parts[0].strip()
            summary = parts[1].strip() if len(parts) > 1 else ""

        # 6) Build output document
        ref_id = req.reference_id
        loc = req.location
        ist = tz.gettz("Asia/Kolkata")
        timestamp = datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

        output_doc = {
            "reference_id": ref_id,
            "timestamp": timestamp,
            "request": user,
            "title": title,
            "summary": summary,
            "boards": [b.dict() for b in board_items],
            "events": request_events,  # Added events from the request
            "location": loc,
            "response_type": "vision_board"
        }

        # 7) Update existing document or insert new one (upsert)
        
        result = db[VISION_BOARD_COLLECTION].update_one(
            {"reference_id": ref_id},  # Filter criteria
            {"$set": output_doc},      # Update with new values
            upsert=True               # Insert if document doesn't exist
        )
        
        # Log the operation result
        if result.matched_count > 0:
            logger.info(f"Updated existing vision board for reference_id: {ref_id}")
        else:
            logger.info(f"Created new vision board for reference_id: {ref_id}")
        
        return output_doc

    except HTTPException:
        raise
    except Exception:
        logger.error("Error in create_vision_board", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error generating vision board")
    

async def get_vision_boards_by_id(reference_id: str) -> List[VisionBoardResponse]:

    logger.info(f"Attempting to retrieve vision boards for reference_id: {reference_id}")
    try:
        # Use .find() to get a cursor of all matching documents
        # Project out the _id field which is an ObjectId and not directly Pydantic compatible
        cursor = db[settings.VISION_BOARD_COLLECTION].find(
            {"reference_id": reference_id},
            {"_id": 0} 
        )

        # Convert cursor to a list of dictionaries
        board_docs = list(cursor)

        if not board_docs:
            logger.warning(f"No vision boards found for reference_id '{reference_id}'.")
            raise HTTPException(status_code=500,detail="No vision boards found for this reference ID")

        logger.info(f"Successfully retrieved {len(board_docs)} vision board(s) for reference_id: {reference_id}")
        
        # Handle backward compatibility for documents that might not have the events field
        for doc in board_docs:
            if "events" not in doc:
                # Try to extract events from the request field if it exists
                if "request" in doc and "events" in doc["request"]:
                    doc["events"] = doc["request"]["events"]
                else:
                    doc["events"] = []  # Default to empty list
            
            # MODIFIED: Handle backward compatibility for vendor_mappings
            for board in doc.get("boards", []):
                if "vendor_mappings" not in board:
                    board["vendor_mappings"] = []  # Default to empty list
        
        # Validate each retrieved document against the VisionBoardResponse Pydantic model
        # This will create a list of VisionBoardResponse objects
        return [VisionBoardResponse(**doc) for doc in board_docs]

    except HTTPException:
        # Re-raise HTTPExceptions (e.g., 404 Not Found)
        raise
    except Exception as e:
        logger.error(f"Error retrieving vision boards for reference_id '{reference_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    
async def get_vision_board_images_by_category(reference_id: str, category: str) -> CategoryImagesResponse:
    """
    Get all image links from vision boards filtered by category (venue, decor, attire)
    Handles frontend-database category name mapping
    """
    
    logger.info(f"Retrieving {category} images for reference_id: {reference_id}")
    
    try:
        # Find all vision boards for the reference_id - MODIFIED: Include title and location fields
        cursor = db[VISION_BOARD_COLLECTION].find(
            {"reference_id": reference_id},
            {"_id": 0, "boards": 1, "title": 1, "location": 1}
        )
        
        board_docs = list(cursor)
        
        if not board_docs:
            logger.warning(f"No vision boards found for reference_id '{reference_id}'")
            raise HTTPException(
                status_code=404, 
                detail="No vision boards found for this reference ID"
            )
        
        # MODIFIED: Collect vendor mappings, titles, and locations from all boards
        all_vendor_mappings = []
        vision_board_titles = []
        locations = []
        
        for doc in board_docs:
            boards = doc.get("boards", [])
            title = doc.get("title", "")
            location = doc.get("location", "")  # Fixed: Get location from doc level, not board level
            
            # Collect title if it exists
            if title:
                vision_board_titles.append(title)
            
            # Collect location if it exists
            if location:
                locations.append(location)
            
            for board in boards:
                vendor_mappings = board.get("vendor_mappings", [])
                all_vendor_mappings.extend(vendor_mappings)
        
        # UPDATED: Enhanced category keyword mapping for frontend-database mismatch
        category_keywords = {
            "venues": ["venues", "venue"],
            "fashion and attire": ["wedding_wear", "bridalWear"],
            "decors": ["decors", "decor"]
        }
        
        keywords = category_keywords.get(category.lower(), [category.lower()])
        
        # MODIFIED: Filter vendor mappings by category using image_link in vendor_mappings
        filtered_vendor_mappings = []
        
        for mapping in all_vendor_mappings:
            image_link = mapping.get("image_link", "")
            
            # Check if any of the category keywords appear in the image link
            if any(keyword.lower() in image_link.lower() for keyword in keywords):
                vendor_id = mapping.get("vendor_id")
                
                # Convert vendor_id to string representation "ObjectId('...')"
                if vendor_id:
                    if isinstance(vendor_id, ObjectId):
                        vendor_id_str = f"ObjectId('{str(vendor_id)}')"
                    else:
                        # If it's already a string, wrap it properly
                        vendor_id_str = f"ObjectId('{vendor_id}')"
                    
                    filtered_vendor_mappings.append(VendorImage(
                        image_link=image_link,
                        vendor_id=vendor_id_str
                    ))
        
        # Remove duplicate vendor mappings based on image_link
        seen_images = set()
        unique_vendor_mappings = []
        for mapping in filtered_vendor_mappings:
            if mapping.image_link not in seen_images:
                unique_vendor_mappings.append(mapping)
                seen_images.add(mapping.image_link)
        
        # MODIFIED: Get unique titles and locations
        unique_titles = list(set(vision_board_titles)) if vision_board_titles else []
        unique_locations = list(set(locations)) if locations else []
        
        # Get the primary location (first unique location or empty string)
        primary_location = unique_locations[0] if unique_locations else ""
        
        logger.info(f"Found {len(unique_vendor_mappings)} unique {category} images for reference_id: {reference_id}")
        logger.info(f"Found {len(unique_titles)} vision board titles: {unique_titles}")
        logger.info(f"Found locations: {unique_locations}")
        
        # MODIFIED: Return response with location included
        return CategoryImagesResponse(
            reference_id=reference_id,
            category=category,
            vendor_mappings=unique_vendor_mappings,
            total_count=len(unique_vendor_mappings),
            location=primary_location,  # Fixed: Use primary_location instead of undefined 'loc'
            titles=unique_titles
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error filtering {category} images for reference_id '{reference_id}': {e}", exc_info=True)
        raise HTTPException
    
def get_category_regex(category: str) -> str:
    """
    Get regex pattern for category matching with broader keyword support
    """
    category_patterns = {
        "venue": r"venue|hall|resort|lawn|garden|beach|hotel|banquet",
        "decor": r"decor|decoration|flower|floral|lighting|backdrop|centerpiece",
        "attire": r"attire|fashion|dress|outfit|clothing|wear|lehenga|saree|suit|gown"
    }
    
    return category_patterns.get(category.lower(), category.lower()) 


# UPDATED: Modified get_vision_board_images_by_event function to include location support
async def get_vision_board_images_by_event(reference_id: str, event: str) -> EventImagesResponse:
    """
    Get all unique image links from vision boards filtered by event
    Extracts from vendor_mappings field when event is present in events field
    Now includes location support
    """
    
    logger.info(f"Retrieving {event} images for reference_id: {reference_id}")
    
    try:
        # Find all vision boards for the reference_id - MODIFIED: Include location field
        cursor = db[VISION_BOARD_COLLECTION].find(
            {"reference_id": reference_id},
            {"_id": 0, "boards": 1, "events": 1, "location": 1, "title": 1}
        )
        
        board_docs = list(cursor)
        
        if not board_docs:
            logger.warning(f"No vision boards found for reference_id '{reference_id}'")
            raise HTTPException(
                status_code=404, 
                detail="No vision boards found for this reference ID"
            )
        
        # Collect vendor mappings from boards that contain the specified event
        all_vendor_mappings = []
        locations = []
        titles = []
        
        for doc in board_docs:
            # Check if the document has the specified event
            doc_events = doc.get("events", [])
            location = doc.get("location", "")
            title = doc.get("title", "")
            
            # Collect location and title
            if location:
                locations.append(location)
            if title:
                titles.append(title)
            
            # Handle different event name formats (case-insensitive matching)
            event_found = False
            if isinstance(doc_events, list):
                for doc_event in doc_events:
                    if isinstance(doc_event, str) and event.lower() in doc_event.lower():
                        event_found = True
                        break
            
            # If event is found, extract vendor mappings from all boards
            if event_found:
                boards = doc.get("boards", [])
                for board in boards:
                    vendor_mappings = board.get("vendor_mappings", [])
                    all_vendor_mappings.extend(vendor_mappings)
        
        if not all_vendor_mappings:
            logger.warning(f"No images found for event '{event}' in reference_id '{reference_id}'")
            # MODIFIED: Include location and titles even when no images found
            unique_locations = list(set(locations)) if locations else []
            unique_titles = list(set(titles)) if titles else []
            primary_location = unique_locations[0] if unique_locations else ""
            
            return EventImagesResponse(
                reference_id=reference_id,
                event=event,
                vendor_mappings=[],
                total_count=0,
                location=primary_location,
                titles=unique_titles
            )
        
        # Convert vendor mappings to VendorImage objects and remove duplicates
        vendor_images = []
        seen_images = set()
        
        for mapping in all_vendor_mappings:
            image_link = mapping.get("image_link", "")
            vendor_id = mapping.get("vendor_id", "")
            
            # Only add if we haven't seen this image link before
            if image_link and image_link not in seen_images:
                # Convert vendor_id to string representation if needed
                if vendor_id:
                    if isinstance(vendor_id, ObjectId):
                        vendor_id_str = f"ObjectId('{str(vendor_id)}')"
                    else:
                        # If it's already a string, keep it as is
                        vendor_id_str = str(vendor_id)
                    
                    vendor_images.append(VendorImage(
                        image_link=image_link,
                        vendor_id=vendor_id_str
                    ))
                    seen_images.add(image_link)
        
        # MODIFIED: Get unique locations and titles
        unique_locations = list(set(locations)) if locations else []
        unique_titles = list(set(titles)) if titles else []
        primary_location = unique_locations[0] if unique_locations else ""
        
        logger.info(f"Found {len(vendor_images)} unique {event} images for reference_id: {reference_id}")
        logger.info(f"Found locations: {unique_locations}")
        logger.info(f"Found titles: {unique_titles}")
        
        return EventImagesResponse(
            reference_id=reference_id,
            event=event,
            vendor_mappings=vendor_images,
            total_count=len(vendor_images),
            location=primary_location,  # ADDED: location field
            titles=unique_titles        # ADDED: titles field
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error filtering {event} images for reference_id '{reference_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {e}")