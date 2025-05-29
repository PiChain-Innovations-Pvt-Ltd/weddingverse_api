# app/services/image_categorization_service.py

import json, re, mimetypes, requests, uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlparse

import google.generativeai as genai
from fastapi import HTTPException

from app.services.vision_board_service import get_matching_boards, create_vision_board
from app.models.vision_board import Color, BoardItem, VisionBoardRequest, VisionBoardResponse
from app.config import GEMINI_API_KEY, VISION_BOARD_COLLECTION
from app.services.mongo_service import db
from app.utils.logger import logger

# … existing Gemini setup …

def _get_gemini_metadata(image_info: Dict[str, Any]) -> Dict[str, Any]:
    # prompt unchanged except: also extract "Colors"
    # (you already have the prompt in your code)
    # expect JSON keys: Wedding Preference, Venue Suits, Wedding Style,
    # Wedding Tone, People Dress Code, Events, Colors
    # (but we’ll ignore Events in extraction)
    # … same as before …
    raw = …  # your existing implementation
    return raw

def _clean_metadata(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Keep only the fields we want from Gemini:
      wedding_preference, venue_suits, wedding_style, wedding_tone,
      people_dress_code, colors (list of color strings)
    """
    mapping = {
      "Wedding Preference": "wedding_preference",
      "Venue Suits":        "venue_suits",
      "Wedding Style":      "wedding_style",
      "Wedding Tone":       "wedding_tone",
      "People Dress Code":  "people_dress_code"
    }
    cleaned = {}
    for ai_key, fk in mapping.items():
        val = raw.get(ai_key)
        cleaned[fk] = val if isinstance(val, str) else ""

    # Extract colors array, but drop descriptions:
    colors = raw.get("Colors", [])
    cleaned["colors"] = [c.get("color") for c in colors if isinstance(c, dict) and c.get("color")]

    return cleaned

def categorize_and_match(
    upload_bytes_list: List[bytes],
    content_types:    List[str],
    image_links:      List[str],
    guest_experience: str,
    events:           List[str],
    limit:            int = 10
) -> List[VisionBoardResponse]:
    results: List[VisionBoardResponse] = []

    # build inputs
    inputs = [{"bytes": b, "content_type": ct, "link": None}
              for b, ct in zip(upload_bytes_list, content_types)]
    inputs += [{"bytes": None, "content_type": None, "link": link}
               for link in image_links]

    for inp in inputs:
        try:
            img_info = _prepare_image_bytes(inp["bytes"], inp["content_type"], inp["link"])
            raw_meta = _get_gemini_metadata(img_info)
            cleaned = _clean_metadata(raw_meta)

            # add user-provided fields
            cleaned["guest_experience"] = guest_experience
            cleaned["events"] = events

            # match on all fields *plus* colors
            docs = get_matching_boards(cleaned, limit=limit)

            # only return image_link
            boards = [BoardItem(image_link=d["image_link"], colors=[]).dict()
                      for d in docs]

            # now get title & summary via create_vision_board
            vb_req = VisionBoardRequest(**{
                **{k: cleaned[k] for k in ["wedding_preference","venue_suits",
                                          "wedding_style","wedding_tone"]},
                "guest_experience": guest_experience,
                "events": events
            })
            vb_out = create_vision_board(vb_req)

            # build response
            vr = VisionBoardResponse(
                reference_id=vb_out["reference_id"],
                timestamp=vb_out["timestamp"],
                request=vb_req,
                title=vb_out["title"],
                summary=vb_out["summary"],
                boards=[BoardItem(image_link=d["image_link"], colors=[]) for d in docs],
                response_type="categorization"
            )

            # persist
            db[VISION_BOARD_COLLECTION].insert_one(vr.dict())

            results.append(vr)

        except HTTPException as he:
            logger.warning("Input skipped: %s", he.detail)
        except Exception:
            logger.error("Error processing image", exc_info=True)

    return results
