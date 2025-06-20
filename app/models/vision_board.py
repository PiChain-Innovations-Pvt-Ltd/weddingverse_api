from pydantic import BaseModel
from typing import List, Optional

class VisionBoardRequest(BaseModel):
    wedding_preference: Optional[str]
    venue_suits:       Optional[str]
    wedding_style:     Optional[str]
    wedding_tone:      Optional[str]
    guest_experience:  Optional[str]
    events:            Optional[List[str]] = []
    location:          Optional[str]
    reference_id:      str

class Color(BaseModel):
    color:       str
    description: Optional[str]

class ImageVendorMapping(BaseModel):
    image_link: str
    vendor_id: str
    
class VendorImage(BaseModel):
    image_link: str
   
class BoardItem(BaseModel):
    colors:      List[str]
    vendor_mappings: List[ImageVendorMapping]

class VisionBoardResponse(BaseModel):
    reference_id: str
    timestamp:    str
    title:        Optional[str]
    summary:      Optional[str]
    boards:       List[BoardItem]
    events:       Optional[List[str]] = [] 
    location:     Optional[str]
    response_type: str

class CategoryImagesResponse(BaseModel):
    reference_id: str
    category: str
    vendor_mappings: List[VendorImage]
    total_count: int 
    titles: List[str] = []
    location: str
    
class EventImagesResponse(BaseModel):
    reference_id: str
    event: str
    vendor_mappings: List[VendorImage]
    total_count: int
    location: Optional[str] = ""     # ADDED: location field
    titles: Optional[List[str]] = [] # ADDED: titles field