import json
import uuid
from datetime import datetime
from dateutil import tz
from typing import List, Dict, Any

from fastapi import HTTPException
from pymongo import ASCENDING
from pymongo.errors import OperationFailure

from app.services.mongo_service import db
from app.config import settings, FIELD_MAP
from app.services.genai_service import model
from app.models.vision_board import Color, BoardItem,VisionBoardRequest,VisionBoardResponse
from app.utils.logger import logger

IMAGE_INPUT_COLLECTION = settings.image_input_collection
OUTPUT_COLLECTION = settings.output_collection

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

def create_vision_board(req) -> Dict[str, Any]:
    try:
        user = req.dict()
        # 1) Fetch matching docs
        docs = get_matching_boards(user, limit=10)

        # 2) Build BoardItem list (convert to model with LIST of image_links)
        board_items = [
            BoardItem(
                image_links=[doc["image_link"]],  # Put single image_link in a list to match model
                colors=[c["color"] for c in doc["data"]["Colors"]]
            )
            for doc in docs
        ]
        
        # Extract key details from matched images for AI context
        dominant_colors = {}
        events = set()
        style_elements = set()
        
        for doc in docs:
            # Extract events from each image
            if "data" in doc and "Events" in doc["data"]:
                for event in doc["data"]["Events"]:
                    events.add(event)
            
            # Count color frequencies
            if "data" in doc and "Colors" in doc["data"]:
                for color_obj in doc["data"]["Colors"]:
                    color = color_obj.get("color")
                    if color:
                        dominant_colors[color] = dominant_colors.get(color, 0) + 1
            
            # Extract venue and style elements if available
            for field in ["Venue Type", "Style Elements", "Decorations", "Theme"]:
                if "data" in doc and field in doc["data"]:
                    if isinstance(doc["data"][field], list):
                        for item in doc["data"][field]:
                            style_elements.add(item)
                    elif doc["data"][field]:
                        style_elements.add(doc["data"][field])

        # Get top colors by frequency
        top_colors = sorted(dominant_colors.items(), key=lambda x: x[1], reverse=True)[:4]
        top_color_names = [color for color, _ in top_colors]
        
        # Format the user preferences in a way that highlights key elements
        formatted_preferences = {}
        priority_fields = {
            "wedding_preference": "Setting",
            "venue_suits": "Venue",
            "wedding_style": "Style",
            "wedding_tone": "Color Palette",
            "guest_experience": "Atmosphere",
            "theme": "Theme",
            "events": "Special Events"
        }
        
        for key, label in priority_fields.items():
            if key in user and user[key]:
                if key == "events" and isinstance(user[key], list):
                    # Handle events list or comma-separated string
                    events_list = []
                    for event in user[key]:
                        if isinstance(event, str) and "," in event:
                            events_list.extend([e.strip() for e in event.split(",") if e.strip()])
                        else:
                            events_list.append(event)
                    formatted_preferences[label] = events_list
                else:
                    formatted_preferences[label] = user[key]
        
        # 3) Prepare enhanced GenAI prompts with more context
        examples = [
            {
                "input": {
                    "Setting": "Outdoor",
                    "Venue": "Garden",
                    "Style": "Classic",
                    "Color Palette": "Pastel",
                    "Atmosphere": "Large Gathering",
                    "Special Events": ["Mehendi", "Haldi"]
                },
                "output": {
                    "title": "Garden Romance",
                    "summary": "This vision board captures a classic, pastel-toned garden wedding designed for a large gathering. The focus is on creating a romantic outdoor ambiance, with pre-wedding events like Mehendi and Haldi adding cultural richness and joyful celebration to the overall experience."
                }
            },
            {
                "input": {
                    "Setting": "Indoor",
                    "Venue": "Ballroom",
                    "Style": "Elegant",
                    "Color Palette": "Gold",
                    "Atmosphere": "Intimate",
                    "Special Events": ["Reception", "Sangeet"]
                },
                "output": {
                    "title": "Golden Intimate Elegance",
                    "summary": "An intimate ballroom celebration bathed in golden warmth, where elegant details create a sophisticated atmosphere. The rich tradition of the Sangeet ceremony blends seamlessly with the refined reception, creating a wedding vision that balances cultural depth with modern luxury."
                }
            }
        ]
        
        system_prompt = (
            "You are a preeminent wedding vision board creator with extraordinary linguistic sophistication and unrivaled expertise in wedding aesthetics, cultural ceremonies, color psychology, and emotional storytelling. "
            "You craft immaculate, elevated prose that transcends ordinary description, employing refined vocabulary and exquisite phrasing befitting the most distinguished celebrations. "
            "You transform wedding_preferences, venue choices, style elements, color palettes, and planned experiences into meticulously articulated narratives "
            "that reflect the couple's vision with exceptional eloquence and poetic sensibility. "
            "Your specialty is creating evocative two-word titles that instantly convey the celebration's essence, "
            "paired with descriptions that weave together venue characteristics, color symbolism, and emotional atmosphere "
            "into sophisticated, captivating narratives using elevated language and metaphorical expression. "
            "You never rely on simple, predictable phrases like 'this celebration' or 'this theme,' instead employing masterful linguistic techniques "
            "to create distinctive, memorable, and refined descriptions worthy of the most elegant weddings."
        )
        
        user_prompt = (
    "Create a vision board title, tagline, and summary based on these preferences:\n\n"
    f"PREFERENCES: {json.dumps(formatted_preferences, indent=2)}\n\n"
    f"PROMINENT COLORS IN SELECTED IMAGES: {', '.join(top_color_names)}\n\n"
    f"STYLE ELEMENTS FROM IMAGES: {', '.join(list(style_elements)[:5]) if style_elements else 'None specified'}\n\n"
    "INSTRUCTIONS:\n"
    "1. FIRST, analyze the deeper meaning behind the couple's preferences (wedding_preference, venue_suits, wedding_style, wedding_tone, guest_experience) and how these elements interweave to create a sublime matrimonial narrative.\n\n"
    "2. TITLE: Craft exactly TWO evocative words that resonate with sophistication and capture the essence of the couple's vision. "
    "The first word should evoke a color, atmosphere, or emotional quality based on their wedding_tone or colors (like 'Gilded' rather than 'Golden'), "
    "while the second word should embody their wedding_style or desired atmosphere (like 'Opulence' rather than 'Elegance'). "
    "Aim for unexpected yet fitting pairings that transcend conventional wedding vocabulary.\n\n"
    "3. TAGLINE: Create a brief descriptive phrase of EXACTLY 7 WORDS that follows this structure: "
    "'A [Style] [Setting] [Event Type] in [Location/Venue]' "
    "For example: 'A Traditional Outdoor Indian Wedding in Bangalore'\n\n"
    "4. SUMMARY: Compose an eloquent paragraph of EXACTLY 42 WORDS that articulates the couple's vision with sophisticated language, including:\n"
    "   - How their wedding_preference and venue_suits create a transcendent atmosphere, employing metaphorical language rather than direct description\n"
    "   - How their chosen color palette enhances the sensory experience, using evocative imagery related to their wedding_tone\n"
    "   - How their wedding_style and planned events will manifest memorable moments, with elevated vocabulary and poetic phrasing\n"
    "   - Construct exactly 2 sentences with complex structure and sophisticated rhythm\n"
    "   - Avoid generic phrases like 'this celebration' or 'this theme' - instead, employ more distinguished and specific language\n"
    "   - Use metaphorical language, elegant compound constructions, and refined vocabulary throughout\n\n"
    "FORMAT YOUR RESPONSE AS JSON: {\"title\": \"Your Title\", \"tagline\": \"Your tagline\", \"summary\": \"Your summary paragraph\"}\n\n"
    "EXAMPLES OF EXCELLENT OUTPUTS:\n" + json.dumps([
        {
            "input": {
                "wedding_preference": "Outdoor",
                "venue_suits": "Beachfront",
                "wedding_style": "Contemporary",
                "wedding_tone": "Intimate",
                "guest_experience": "Immersive Celebration",
                "events": ["Wedding Ceremony", "Cocktail Hour", "Sunset Reception"],
                "colors": ["Azure Blue", "Coral", "Silver", "Ivory", "Teal"]
            },
            "output": {
                "title": "Coastal Serenity",
                "tagline": "A Contemporary Beachfront Wedding in Goa",
                "summary": "Oceanic vistas embrace modernist sensibilities along tranquil shores, where intimate moments crystallize into eternal remembrances against horizon's amber canvas. Azure wavelets merge with coral undertones amidst argentate accents, orchestrating a symphony of maritime elegance beneath celestial canopies illuminated by twilight's tender glow."
            }
        },
        {
            "input": {
                "wedding_preference": "Indoor",
                "venue_suits": "Heritage Mansion",
                "wedding_style": "Royal",
                "wedding_tone": "Opulent",
                "guest_experience": "Regal Indulgence",
                "events": ["Sangeet", "Traditional Ceremony", "Grand Reception"],
                "colors": ["Burgundy", "Gold", "Emerald", "Ivory", "Purple"]
            },
            "output": {
                "title": "Velvet Majesty",
                "tagline": "A Royal Heritage Celebration in Jaipur",
                "summary": "Ancestral corridors transform into palatial splendor where temporal boundaries dissolve, ushering attendees into realms of aristocratic grandeur and romantic reverie. Burgundy tapestries interwoven with gilded threads cascade among emerald embellishments beneath sculptured ceilings, conjuring a sovereign ambiance honoring dynastic traditions with contemporary magnificence."
            }
        },
        {
            "input": {
                "wedding_preference": "Outdoor",
                "venue_suits": "Beach",
                "wedding_style": "Classic",
                "wedding_tone": "Monochrome",
                "guest_experience": "Large Gathering",
                "events": ["Engagement Party", "Sangeet"]
            },
            "output": {
                "title": "Seaside Grandeur",
                "tagline": "A Classic Outdoor Beach Wedding in Goa",
                "summary": "Coastal horizons frame an opulent matrimonial canvas where expansive gatherings converge amidst pristine shorelines, embodying timeless sophistication. Monochromatic hues cascade across ceremonial spaces, while engagement revelries and vibrant Sangeet festivities orchestrate an exquisite symphony of matrimonial jubilation."
            }
        }
    ], indent=2)
)

        # 4) Call the model with enhanced prompts
        try:
            # Set temperature for creativity but with enough structure for consistency
            resp = model.generate_content(
                [system_prompt, user_prompt],
                generation_config={
                    "temperature": 0.6,
                    "max_output_tokens": 300,
                    "top_p": 0.95,
                    "top_k": 40
                }
            )
            text = resp.text.strip()
        except Exception:
            logger.error("GenAI call failed", exc_info=True)
            raise HTTPException(status_code=502, detail="Failed to generate vision board summary")

        # 5) Improved JSON parsing with better fallbacks
        try:
            # Strip markdown code blocks if present
            if "```" in text:
                parts = text.split("```")
                if len(parts) >= 3:
                    json_text = parts[1]
                    if json_text.startswith("json"):
                        json_text = json_text[4:].strip()
                    else:
                        json_text = json_text.strip()
                    text = json_text
            
            parsed = json.loads(text)
            title = parsed.get("title", "").strip()
            summary = parsed.get("summary", "").strip()
            
            # Validate and improve title if needed
            if not title or len(title.split()) > 5:
                venue = formatted_preferences.get("Venue", "")
                style = formatted_preferences.get("Style", "")
                setting = formatted_preferences.get("Setting", "")
                
                elements = [e for e in [style, venue, setting] if e]
                if elements:
                    fallback_title = " ".join(elements[:2]).title()
                    logger.warning(f"Using constructed title: {fallback_title}")
                    title = fallback_title
                else:
                    fallback_title = f"{top_color_names[0].capitalize() if top_color_names else 'Elegant'} Celebration"
                    logger.warning(f"Using color-based fallback title: {fallback_title}")
                    title = fallback_title
                
            # Validate and improve summary if needed
            if not summary or len(summary) < 50:
                elements = []
                
                if "Venue" in formatted_preferences and "Setting" in formatted_preferences:
                    elements.append(f"a {formatted_preferences['Setting'].lower()} wedding in a {formatted_preferences['Venue'].lower()} setting")
                elif "Venue" in formatted_preferences:
                    elements.append(f"a {formatted_preferences['Venue'].lower()} wedding")
                elif "Setting" in formatted_preferences:
                    elements.append(f"a {formatted_preferences['Setting'].lower()} wedding")
                
                if "Style" in formatted_preferences and "Color Palette" in formatted_preferences:
                    elements.append(f"featuring a {formatted_preferences['Style'].lower()} style with a {formatted_preferences['Color Palette'].lower()} color palette")
                elif "Style" in formatted_preferences:
                    elements.append(f"featuring a {formatted_preferences['Style'].lower()} style")
                elif "Color Palette" in formatted_preferences:
                    elements.append(f"featuring a {formatted_preferences['Color Palette'].lower()} color palette")
                
                if "Atmosphere" in formatted_preferences:
                    elements.append(f"designed for a {formatted_preferences['Atmosphere'].lower()}")
                
                if "Special Events" in formatted_preferences and formatted_preferences["Special Events"]:
                    events_list = formatted_preferences["Special Events"]
                    events_text = ", ".join(events_list[:-1]) + (" and " if len(events_list) > 1 else "") + events_list[-1] if events_list else ""
                    if events_text:
                        elements.append(f"with special celebrations including {events_text}")
                
                fallback_summary = "This vision board captures " + ", ".join(elements) + "."
                logger.warning(f"Using structured fallback summary")
                summary = fallback_summary
                
        except (json.JSONDecodeError, IndexError, KeyError) as e:
            logger.warning(f"Failed to parse model output as JSON: {e}", exc_info=True)
            
            # Extract title and summary using text parsing
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            
            title_line = next((line for line in lines if "title" in line.lower() and ":" in line), "")
            if title_line:
                title_parts = title_line.split(":", 1)
                if len(title_parts) > 1:
                    title = title_parts[1].strip().strip('"\'')
            
            summary_line = next((line for line in lines if "summary" in line.lower() and ":" in line), "")
            if summary_line:
                summary_parts = summary_line.split(":", 1)
                if len(summary_parts) > 1:
                    summary = summary_parts[1].strip().strip('"\'')
            
            # If still not found, use the longest line as summary and shortest as title
            if not title or not summary:
                if lines:
                    lines_by_length = sorted(lines, key=len)
                    if not title and len(lines_by_length[0]) < 30:
                        title = lines_by_length[0]
                    if not summary and len(lines_by_length[-1]) > 50:
                        summary = lines_by_length[-1]
            
            # Apply default fallbacks if still empty
            if not title:
                title = f"{formatted_preferences.get('Style', 'Elegant')} {formatted_preferences.get('Venue', 'Wedding')}"
            
            if not summary:
                venue = formatted_preferences.get("Venue", "beautiful")
                style = formatted_preferences.get("Style", "personalized")
                color = formatted_preferences.get("Color Palette", top_color_names[0] if top_color_names else "elegant")
                summary = f"A vision board showcasing a {style.lower()} wedding in a {venue.lower()} setting with a {color.lower()} color palette that perfectly captures the couple's unique style and preferences."

        # 6) Build output document with enhanced metadata
        ref_id = str(uuid.uuid4())
        ist = tz.gettz("Asia/Kolkata")
        timestamp = datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

        # Create VisionBoardResponse using the models
        output_doc = VisionBoardResponse(
            reference_id=ref_id,
            timestamp=timestamp,
            request=req,  # Already a VisionBoardRequest
            title=title,
            summary=summary,
            boards=board_items,  # Already a list of BoardItem objects
            response_type="vision_board"
        )

        # 7) Persist the response to database
        # Convert to dict for MongoDB storage
        db[OUTPUT_COLLECTION].insert_one(output_doc.dict())
        
        # 8) Return the response
        return output_doc.dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in create_vision_board", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error generating vision board")
