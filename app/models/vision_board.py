from pydantic import BaseModel
from typing import List, Optional

class VisionBoardRequest(BaseModel):
    wedding_preference: Optional[str]
    venue_suits:       Optional[str]
    wedding_style:     Optional[str]
    wedding_tone:      Optional[str]
    guest_experience:  Optional[str]
    events:            Optional[List[str]] = []
    reference_id:      str

class Color(BaseModel):
    color:       str
    description: Optional[str]

class BoardItem(BaseModel):
    image_links: List[str]
    colors:      List[str]

class VisionBoardResponse(BaseModel):
    reference_id: str
    timestamp:    str
    request:      VisionBoardRequest
    title:        Optional[str]
    summary:      Optional[str]
    boards:       List[BoardItem]
    response_type:str
