import json
import re
import mimetypes
import requests

from typing import List, Optional, Dict, Any
from datetime import datetime
from dateutil import tz
from urllib.parse import urlparse
from bson import ObjectId

import google.generativeai as genai
import vertexai
from vertexai.preview.generative_models import GenerativeModel, Part
from google.oauth2 import service_account
from fastapi import HTTPException

from app.services.vision_board_service import get_matching_boards
from app.models.vision_board import VisionBoardRequest, VisionBoardResponse, BoardItem, ImageVendorMapping
from app.config import settings
from app.services.mongo_service import db
from app.utils.logger import logger

GEMINI_API_KEY = settings.gemini_api_key
VISION_BOARD_COLLECTION = settings.VISION_BOARD_COLLECTION

# ─── Gemini setup ───────────────────────────────────────────────────────────────
genai.configure(api_key=GEMINI_API_KEY)
try:
    credentials = service_account.Credentials.from_service_account_info(settings.GOOGLE_APPLICATION_CREDENTIALS)
    vertexai.init(project=settings.PROJECT_ID, location=settings.REGION, credentials=credentials)
    logger.info("Vertex AI initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize Vertex AI: {e}")
    raise RuntimeError(f"Failed to initialize Vertex AI: {e}. Application cannot proceed.")

IMG_MODEL_CONFIG = {
    "temperature":       0.2,
    "top_p":             1,
    "top_k":             32,
    "max_output_tokens": 4096,
}

model = GenerativeModel(
    model_name=settings.MODEL_NAME,
    generation_config=IMG_MODEL_CONFIG
)

def _prepare_image_bytes(
    upload_bytes: Optional[bytes],
    upload_content_type: Optional[str],
    image_link: Optional[str]
) -> Dict[str, Any]:
    """
    Return mime+bytes for an uploaded file or a URL, validating the link scheme.
    """
    if upload_bytes is not None:
        return {
            "mime_type": upload_content_type or "application/octet-stream",
            "data": upload_bytes
        }

    if image_link:
        parsed = urlparse(image_link)
        if parsed.scheme not in ("http", "https"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid URL (must include http:// or https://): {image_link}"
            )
        try:
            resp = requests.get(image_link, timeout=5)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise HTTPException(status_code=400, detail=f"Could not fetch image: {e}")
        mime = resp.headers.get("Content-Type") \
               or mimetypes.guess_type(image_link)[0] \
               or "application/octet-stream"
        return {"mime_type": mime, "data": resp.content}

    raise HTTPException(
        status_code=400,
        detail="No image provided; upload a file or include image_link"
    )


def _get_gemini_metadata(image_info: Dict[str, Any]) -> Dict[str, Any]:

    system_prompt = (
        "You are an AI that categorizes wedding images into specific "
        "categories based on visual details and context."
    )

    user_prompt = """
        Analyze the image provided and predict the wedding attributes using these guidelines:

        1. **Wedding Preference**: 
        - Is the wedding setup primarily **Outdoor** or **Indoor**? Look for natural elements like beaches, gardens, or open skies for outdoor settings, or enclosed spaces like halls or modern architecture for indoor settings.

        2. **Venue Suits**: 
        - Based on visible elements, classify the venue as one of the following:
            - **Beach**: Includes sand, sea, trees, or coastal views.
            - **Garden**: Features greenery, flowers, lawns, or natural landscapes.
            - **Modern Space**: Includes contemporary structures, geometric designs, or clean urban layouts.
            - **Floral**: Emphasis on flower arrangements or floral-themed decor.
            - **Palace**: Includes large traditional structures, ornate details, or grand historic settings.

        3. **Wedding Style**: 
        - Based on the decorations, props, or overall aesthetic, classify the style as:
            - **Boho**: Rustic, free-spirited, natural tones, macramé, or wooden props.
            - **Classic**: Elegant, timeless, with formal setups or traditional decor.
            - **Modern**: Sleek, minimalistic, with bold or contemporary designs.
            - **Rustic**: Warm, earthy tones, rural or vintage elements.
            - **Bollywood**: Vibrant, glamorous, with an emphasis on cultural grandeur.

        4. **Wedding Tone**: 
        - Analyze the color palette and overall mood:
            - **Pastel**: Soft, light tones like blush, mint, or lavender.
            - **Vibrant Hue**: Bright, bold colors like reds, yellows, or greens.
            - **Monochrome**: Black-and-white or shades of a single color.
            - **Metallic**: Use of gold, silver, or metallic accents.
        
        5. **Colors**:
        - Identify all distinct colors visible in the image and describe which part of the image corresponds to each color.
        Return these as an array of objects where each object has two keys: "color" and "description" (for example: [{"color": "red", "description": "The bridesmaid dresses"}, {"color": "blue", "description": "The sky background"}]). If no prominent colors are detected, return an empty array.


        Return the output in JSON format using the following structure:
        {
            "Wedding Preference": "",
            "Venue Suits": "",
            "Wedding Style": "",
            "Wedding Tone": "",
            "Colors": []
        }
        Ensure "Colors" are always returned as lists, even if empty.
    """
    try:
        image_info = Part.from_data(data=image_info["data"], mime_type=image_info["mime_type"])
        resp = model.generate_content([system_prompt, image_info, user_prompt])
        text = resp.text.strip()
    except Exception:
        logger.error("Gemini image call failed", exc_info=True)
        raise HTTPException(
            status_code=502,
            detail="Failed to extract image metadata"
        )

    # strip ``` fences
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        text = "\n".join([ln for ln in lines if not ln.strip().startswith("```")]).strip()

    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise HTTPException(status_code=502, detail="AI did not return JSON")
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="Invalid JSON from AI")


def _clean_metadata(raw: Dict[str, Any]) -> Dict[str, Any]:
    mapping = {
      "Wedding Preference": "wedding_preference",
      "Venue Suits":        "venue_suits",
      "Wedding Style":      "wedding_style",
      "Wedding Tone":       "wedding_tone"
    }
    cleaned = {}
    for ai_key, fk in mapping.items():
        val = raw.get(ai_key)
        cleaned[fk] = val if isinstance(val, str) else ""

    # Extract colors array, but drop descriptions:
    colors = raw.get("Colors", [])
    cleaned["colors"] = [c.get("color") for c in colors if isinstance(c, dict) and c.get("color")]

    return cleaned


async def categorize_and_match(
    upload_bytes_list: List[bytes],
    content_types:    List[str],
    guest_experience: str,
    events:           List[str],
    reference_id:     str,
    location:         Optional[str] = None,  # ADDED: location parameter
    limit:            int = 10
) -> List[Dict[str, Any]]:

    for img_bytes, content_type in zip(upload_bytes_list, content_types):
        try:
            img_info = _prepare_image_bytes(img_bytes, content_type, None)
            raw_meta = _get_gemini_metadata(img_info)
            cleaned  = _clean_metadata(raw_meta)
            cleaned["guest_experience"] = guest_experience
            cleaned["events"]           = events

            docs = get_matching_boards(cleaned, limit=limit)
            colors = cleaned.get("colors", [])

            # MODIFIED: collect image_links and create vendor mappings (same as vision board logic)
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

            # MODIFIED: instantiate BoardItem with vendor mappings (same as vision board logic)
            board_items = [
                BoardItem(
                    colors=colors,
                    vendor_mappings=vendor_mappings
                )
            ]

            # Prepare prompts
            vb_req = VisionBoardRequest(
                reference_id=      reference_id,
                wedding_preference=cleaned["wedding_preference"],
                venue_suits=       cleaned["venue_suits"],
                wedding_style=     cleaned["wedding_style"],
                wedding_tone=      cleaned["wedding_tone"],
                guest_experience=  cleaned["guest_experience"],
                events=            cleaned["events"],
            )
            user_input   = json.dumps(vb_req.dict(), indent=2)
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

            # Call Gemini
            try:
                resp = model.generate_content([system_prompt, user_prompt])
                text = resp.text.strip()
            except Exception:
                logger.error("GenAI call failed", exc_info=True)
                raise HTTPException(502, "Failed to generate vision board summary")

            # Strip fences & parse
            if text.startswith("```") and text.endswith("```"):
                lines = text.splitlines()
                text = "\n".join([ln for ln in lines if not ln.strip().startswith("```")]).strip()
            try:
                parsed  = json.loads(text)
                title   = parsed.get("title","").strip()
                summary = parsed.get("summary","").strip()
            except json.JSONDecodeError:
                parts   = text.split("\n",1)
                title   = parts[0].strip()
                summary = parts[1].strip() if len(parts)>1 else ""

            # Build output
            ist      = tz.gettz("Asia/Kolkata")
            timestamp= datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

            # MODIFIED: Build output document with vendor mappings and location
            output = {
                "reference_id": reference_id,
                "timestamp": timestamp,
                "request": vb_req.dict(),
                "title": title,
                "summary": summary,
                "boards": [b.dict() for b in board_items],
                "events": events,
                "location": location or "",  # ADDED: location field
                "response_type": "categorization"
            }

            result = db[VISION_BOARD_COLLECTION].update_one(
                {"reference_id": reference_id, "response_type": "categorization"},
                {"$set": output},
                upsert=True
            )
            
            # Log the operation result
            if result.matched_count > 0:
                logger.info(f"Updated existing categorization for reference_id: {reference_id}")
            else:
                logger.info(f"Created new categorization for reference_id: {reference_id}")
            return output

        except HTTPException as he:
            logger.warning("Image skipped: %s", he.detail)
        except Exception:
            logger.error("Error processing image", exc_info=True)

    return output


async def categorize_bulk(
    upload_bytes_list: List[bytes],
    content_types:    List[str],
    guest_experience: str,
    events:           List[str],
    reference_id:     str,
    location:         Optional[str] = None,  # ADDED: location parameter
    limit:            int = 10
) -> Dict[str, Any]:

    # 1) Prepare a list of image_info dicts
    image_infos = [
        Part.from_data(data=b, mime_type=ct)
        for b, ct in zip(upload_bytes_list, content_types)
    ]

    # 2) Call Gemini once, passing all images in the prompt
    #    (Gemini supports a list where each element can be an image blob)
    try:
        system_prompt = "You are an AI that categorizes multiple wedding images into unified metadata based on visual details and context."
        user_prompt = """
        Analyze the image provided and predict the wedding attributes using these guidelines:

        1. **Wedding Preference**: 
        - Is the wedding setup primarily **Outdoor** or **Indoor**? Look for natural elements like beaches, gardens, or open skies for outdoor settings, or enclosed spaces like halls or modern architecture for indoor settings.

        2. **Venue Suits**: 
        - Based on visible elements, classify the venue as one of the following:
            - **Beach**: Includes sand, sea, trees, or coastal views.
            - **Garden**: Features greenery, flowers, lawns, or natural landscapes.
            - **Modern Space**: Includes contemporary structures, geometric designs, or clean urban layouts.
            - **Floral**: Emphasis on flower arrangements or floral-themed decor.
            - **Palace**: Includes large traditional structures, ornate details, or grand historic settings.

        3. **Wedding Style**: 
        - Based on the decorations, props, or overall aesthetic, classify the style as:
            - **Boho**: Rustic, free-spirited, natural tones, macramé, or wooden props.
            - **Classic**: Elegant, timeless, with formal setups or traditional decor.
            - **Modern**: Sleek, minimalistic, with bold or contemporary designs.
            - **Rustic**: Warm, earthy tones, rural or vintage elements.
            - **Bollywood**: Vibrant, glamorous, with an emphasis on cultural grandeur.

        4. **Wedding Tone**: 
        - Analyze the color palette and overall mood:
            - **Pastel**: Soft, light tones like blush, mint, or lavender.
            - **Vibrant Hue**: Bright, bold colors like reds, yellows, or greens.
            - **Monochrome**: Black-and-white or shades of a single color.
            - **Metallic**: Use of gold, silver, or metallic accents.
        
        5. **Colors**:
        - Identify all distinct colors visible in the image and describe which part of the image corresponds to each color.
        Return these as an array of objects where each object has two keys: "color" and "description" (for example: [{"color": "red", "description": "The bridesmaid dresses"}, {"color": "blue", "description": "The sky background"}]). If no prominent colors are detected, return an empty array.


        Return the output in JSON format using the following structure:
        {
            "Wedding Preference": "",
            "Venue Suits": "",
            "Wedding Style": "",
            "Wedding Tone": "",
            "Colors": []
        }
        Ensure "Colors" are always returned as lists, even if empty.
    """
        resp = model.generate_content([system_prompt, *image_infos, user_prompt])
        text = resp.text.strip()
    except Exception:
        logger.error("Bulk Gemini call failed", exc_info=True)
        raise HTTPException(502, "Failed to extract combined metadata from images")

    # 3) Strip fences & parse JSON
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        text = "\n".join([ln for ln in lines if not ln.strip().startswith("```")]).strip()
    try:
        raw_meta = json.loads(text)
    except json.JSONDecodeError:
        raise HTTPException(502, "Invalid JSON from AI for bulk images")

    # 4) Clean exactly like single‐image
    cleaned = _clean_metadata(raw_meta)
    cleaned["guest_experience"] = guest_experience
    cleaned["events"]           = events

    # 5) Match + build boards, title/summary exactly as in categorize_and_match
    docs = get_matching_boards(cleaned, limit=limit)
    colors = cleaned.get("colors", [])

    # MODIFIED: collect image_links and create vendor mappings (same as vision board logic)
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

    # MODIFIED: instantiate BoardItem with vendor mappings (same as vision board logic)
    board_items = [
        BoardItem(
            colors=colors,
            vendor_mappings=vendor_mappings
        )
    ]

    vb_req = VisionBoardRequest(
        reference_id=      reference_id,
        wedding_preference=cleaned["wedding_preference"],
        venue_suits=       cleaned["venue_suits"],
        wedding_style=     cleaned["wedding_style"],
        wedding_tone=      cleaned["wedding_tone"],
        guest_experience=  guest_experience,
        events=            events,
    )
    # build vision‐board title/summary once
    user_input   = json.dumps(vb_req.dict(), indent=2)
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
    try:
        resp = model.generate_content([system_prompt, user_prompt])
        text = resp.text.strip()
    except Exception:
        logger.error("GenAI vision-board call failed", exc_info=True)
        raise HTTPException(502, "Failed to generate vision board summary")

    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        text = "\n".join([ln for ln in lines if not ln.strip().startswith("```")]).strip()
    try:
        parsed = json.loads(text)
        title   = parsed.get("title","").strip()
        summary = parsed.get("summary","").strip()
    except:
        parts   = text.split("\n",1)
        title   = parts[0].strip()
        summary = parts[1].strip() if len(parts)>1 else ""

    # 6) Build and persist a single output
    ist       = tz.gettz("Asia/Kolkata")
    timestamp = datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

    # MODIFIED: Build output document with vendor mappings and location
    output = {
        "reference_id": reference_id,
        "timestamp": timestamp,
        "request": vb_req.dict(),
        "title": title,
        "summary": summary,
        "boards": [b.dict() for b in board_items],
        "events": events,
        "location": location or "",  # ADDED: location field
        "response_type": "categorization"
    }
    
    # persist & strip _id
    result = db[VISION_BOARD_COLLECTION].update_one(
        {"reference_id": reference_id, "response_type": "categorization"},
        {"$set": output},
        upsert=True
    )
    
    # Log the operation result
    if result.matched_count > 0:
        logger.info(f"Updated existing bulk categorization for reference_id: {reference_id}")
    else:
        logger.info(f"Created new bulk categorization for reference_id: {reference_id}")

    return output