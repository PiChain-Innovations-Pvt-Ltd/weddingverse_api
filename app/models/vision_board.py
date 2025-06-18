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

class ImageVendorMapping(BaseModel):
    image_link: str
    vendor_id: str

class BoardItem(BaseModel):
    #image_links: List[str]
    colors:      List[str]
    vendor_mappings: List[ImageVendorMapping]  # New field for vendor mapping

class VisionBoardResponse(BaseModel):
    reference_id: str
    timestamp:    str
    title:        Optional[str]
    summary:      Optional[str]
    boards:       List[BoardItem]
    events:       Optional[List[str]] = [] 
    response_type: str

class CategoryImagesResponse(BaseModel):
    reference_id: str
    category: str
    #image_links: List[str]
    vendor_mappings: List[ImageVendorMapping]  # New field for vendor mapping
    total_count: int