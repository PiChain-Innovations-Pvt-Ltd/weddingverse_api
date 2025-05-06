import os, json, uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List, Optional
import uvicorn

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
import google.generativeai as genai

# ─── Gemini setup ──────────────────────────────────────────────────────────────
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    generation_config={
        "temperature":0.2,
        "top_p":1, 
        "top_k":32,
        "max_output_tokens":4096
    }
)

# ---------------------------
# MongoDB Configuration
# ---------------------------
MONGO_URI = "mongodb://localhost:27017"
DATABASE_NAME = "data"
COLLECTION_INPUT = "image_description"
COLLECTION_OUTPUT = "weddingverse_output"

# Set up MongoDB client
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[DATABASE_NAME]
collection_in = db[COLLECTION_INPUT]
collection_out = db[COLLECTION_OUTPUT]

# ─── Pydantic models ───────────────────────────────────────────────────────────
class VisionBoardRequest(BaseModel):
    wedding_preference: Optional[str]
    venue_suits:       Optional[str]
    wedding_style:     Optional[str]
    wedding_tone:      Optional[str]
    guest_experience:  Optional[str]
    people_dress_code: Optional[str]
    events:            Optional[List[str]] = []

class Color(BaseModel):
    color:       str
    description: str

class BoardItem(BaseModel):
    image_link: str
    colors:     List[Color]

class VisionBoardResponse(BaseModel):
    reference_id: str
    timestamp:    str
    title:        str
    summary:      str
    boards:       List[BoardItem]

# ─── Field map for your Mongo “data.” keys ──────────────────────────────────────
FIELD_MAP = {
    "wedding_preference": "data.Wedding Preference",
    "venue_suits":        "data.Venue Suits",
    "wedding_style":      "data.Wedding Style",
    "wedding_tone":       "data.Wedding Tone",
    "guest_experience":   "data.Guest Experience",
    "people_dress_code":  "data.People Dress Code",
}

# ─── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI()

@app.post("/vision-board", response_model=VisionBoardResponse)
def vision_board(req: VisionBoardRequest):
    user = req.dict()
    # build Mongo query
    query = {}
    for in_key, db_field in FIELD_MAP.items():
        if user.get(in_key):
            query[db_field] = user[in_key]
    if user["events"]:
        query["data.Events"] = {"$all": user["events"]}

    # fetch matching boards
    cursor = collection_in.find(query, {"image_link":1,"data.Colors":1,"_id":0})
    boards = [
        BoardItem(
          image_link=doc["image_link"],
          colors=[Color(**c) for c in doc["data"]["Colors"]]
        )
        for doc in cursor
    ]

    user_input = json.dumps(user, indent=2)

    # generate title & summary via Gemini
    system_prompt = '''
        You are a helpful assistant that crafts an evocative title and concise summary for a wedding vision board.
    '''
    
    user_prompt = f'''
        Generate a short, expressive title (max 2 words) and a one-paragraph summary for this wedding vision board selection. 
        Return output as JSON with keys 'title' and 'summary'.
        Input:{user_input}
    '''
    resp = model.generate_content([system_prompt, user_prompt])
    text = resp.text.strip()

    # remove markdown code fences if present
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        content_lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text = "\n".join(content_lines).strip()

    # parse JSON response
    try:
        data = json.loads(text)
        title = data.get("title", "")
        summary = data.get("summary", "")
    except json.JSONDecodeError:
        lines = text.split("\n", 1)
        title = lines[0].strip()
        summary = lines[1].strip() if len(lines) > 1 else ""

    # generate reference ID and IST timestamp
    ref_id = str(uuid.uuid4())
    ist_tz = ZoneInfo("Asia/Kolkata")
    timestamp = datetime.now(ist_tz).strftime("%Y-%m-%d %H:%M:%S %Z%z")

    # prepare output document
    output_doc = {
        "reference_id": ref_id,
        "timestamp": timestamp,
        "request": user,
        "title": title,
        "summary": summary,
        "boards": [b.dict() for b in boards]
    }
    # store in weddingverse_output collection
    collection_out.insert_one(output_doc)

    return VisionBoardResponse(**output_doc)

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
