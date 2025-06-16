import json
from datetime import datetime
from dateutil import tz

from fastapi import HTTPException
from pymongo import ASCENDING
from pymongo.errors import OperationFailure
from typing import List

from app.services.mongo_service import db
from app.config import settings, FIELD_MAP
from app.services.genai_service import model
from app.models.vision_board import BoardItem, VisionBoardRequest, VisionBoardResponse
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
        conds.append({
            "$cond": [{"$in": [ev, "$data.Events"]}, 1, 0]
        })
        criteria.append(("event", ev, None, "data.Events"))

    for clr in colors:
        conds.append({
            "$cond": [{"$in": [clr, "$colorList"]}, 1, 0]
        })
        criteria.append(("color", clr, None, "data.Colors"))

    total_fields = len(conds)

    pipeline = [
        {
            "$addFields": {
                "colorList": {
                    "$map": {
                        "input": "$data.Colors",
                        "as": "c",
                        "in": "$$c.color"
                    }
                }
            }
        },
        {
            "$addFields": {
                "matchCount": {"$add": conds}
            }
        },
        {"$sort": {"matchCount": -1}},
        {
            "$project": {
                "_id": 0,
                "image_link": 1,
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
                   .find({}, {"_id": 0, "image_link": 1, "data.Colors": 1}) \
                   .sort("_id", ASCENDING).limit(limit)
        return [{**d, "matchCount": 0} for d in cursor]

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
            )["data"]

            matched_names = []

            for key in provided:
                data_key = FIELD_MAP[key].split(".", 1)[1]
                if full_doc.get(data_key) == user[key]:
                    matched_names.append(f"{key}={user[key]}")

            for ev in events:
                if ev in full_doc.get("Events", []):
                    matched_names.append(f"event:{ev}")

            for clr in colors:
                color_values = [c.get("color") for c in full_doc.get("Colors", [])]
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
                   .find({}, {"_id": 0, "image_link": 1, "data.Colors": 1}) \
                   .sort("_id", ASCENDING).limit(limit)
        docs = [{**d, "matchCount": 0} for d in cursor]

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

        # collect every image_link
        image_links = [doc["image_link"] for doc in docs]

        # flatten + dedupe every color
        color_set = {
            c["color"]
            for doc in docs
            for c in doc["data"]["Colors"]
        }
        colors = list(color_set)

        # instantiate one BoardItem
        board_items = [
            BoardItem(
                image_links=image_links,
                colors=      colors
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
            "response_type": "vision_board"
        }

        # 7) Persist and return
        db[VISION_BOARD_COLLECTION].insert_one(output_doc)
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
        
        # Validate each retrieved document against the VisionBoardResponse Pydantic model
        # This will create a list of VisionBoardResponse objects
        return [VisionBoardResponse(**doc) for doc in board_docs]

    except HTTPException:
        # Re-raise HTTPExceptions (e.g., 404 Not Found)
        raise
    except Exception as e:
        logger.error(f"Error retrieving vision boards for reference_id '{reference_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
