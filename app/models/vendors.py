# # # app/models/vendors.py
# # from pydantic import BaseModel, Field, ConfigDict, field_validator, field_serializer
# # from typing import List, Optional, Dict, Union
# # from bson import ObjectId

# # class VendorItem(BaseModel):
# #     # Required field - generated using hash-based approach for security
# #     vendor_id: str = Field(..., description="Unique identifier for the vendor (hash-based, not MongoDB ObjectId)")
    
# #     title: str = Field(..., alias="Title", description="Vendor title/name")
    
# #     # Rating can be None (displayed as "Not Available") or float value
# #     rating: Optional[float] = Field(None, alias="Rating", description="Vendor rating as a float or null for Not Available")
    
# #     image_urls: Optional[List[str]] = Field(None, alias="Image URLs", description="List of vendor image URLs")
    
# #     city: Optional[str] = Field(None, alias="City", description="Vendor city location")
    
# #     # Handle ObjectId conversion (for backward compatibility)
# #     @field_validator('vendor_id', mode='before')
# #     @classmethod
# #     def convert_objectid(cls, v):
# #         if isinstance(v, ObjectId):
# #             return str(v)
# #         return v
    
# #     # Custom serializer for rating to show "Not Available" for None values
# #     @field_serializer('rating')
# #     def serialize_rating(self, rating: Optional[float]) -> Union[float, str]:
# #         if rating is None:
# #             return "Not Available"
# #         return rating

# #     model_config = ConfigDict(populate_by_name=True, extra='ignore')


# # class ExploreVendorsResponse(BaseModel):
# #     category_name: str = Field(..., description="The vendor category being explored")
# #     location: str = Field(..., description="The wedding location from budget plan")
# #     vendors: List[VendorItem] = Field(..., description="List of vendors for current page")
# #     page: int = Field(..., description="Current page number")
# #     limit: int = Field(..., description="Number of vendors per page")
# #     total_vendors: int = Field(..., description="Total count of vendors matching criteria")
# #     total_pages: int = Field(..., description="Total number of pages")
    
# #     class Config:
# #         json_schema_extra = {
# #             "example": {
# #                 "category_name": "venues",
# #                 "location": "Bengaluru",
# #                 "vendors": [
# #                     {
# #                         "vendor_id": "VEN_a1b2c3d4e5f6",
# #                         "title": "Galaxy Club",
# #                         "rating": 5.0,
# #                         "image_urls": ["https://example.com/image1.jpg"],
# #                         "city": "Bengaluru"
# #                     },
# #                     {
# #                         "vendor_id": "VEN_x7y8z9m3n4p5",
# #                         "title": "Royal Palace",
# #                         "rating": "Not Available",
# #                         "image_urls": None,
# #                         "city": "Bengaluru"
# #                     }
# #                 ],
# #                 "page": 1,
# #                 "limit": 10,
# #                 "total_vendors": 25,
# #                 "total_pages": 3
# #             }
# #         }




# # weddingverse_api15/app/models/vendors.py
# from pydantic import BaseModel, Field, ConfigDict, field_validator, field_serializer
# from typing import List, Optional, Dict, Union
# from bson import ObjectId

# class VendorItem(BaseModel):
#     # Required field - generated using hash-based approach for security
#     vendor_id: str = Field(..., description="Unique identifier for the vendor (hash-based, not MongoDB ObjectId)")
    
#     title: str = Field(..., alias="Title", description="Vendor title/name")
    
#     # Rating can be None (displayed as "Not Available") or float value
#     rating: Optional[float] = Field(None, alias="Rating", description="Vendor rating as a float or null for Not Available")
    
#     image_urls: Optional[List[str]] = Field(None, alias="Image URLs", description="List of vendor image URLs")
    
#     city: Optional[str] = Field(None, alias="City", description="Vendor city location")
    
#     # Handle ObjectId conversion (for backward compatibility)
#     @field_validator('vendor_id', mode='before')
#     @classmethod
#     def convert_objectid(cls, v):
#         if isinstance(v, ObjectId):
#             return str(v)
#         return v
    
#     # Custom serializer for rating to show "Not Available" for None values
#     @field_serializer('rating')
#     def serialize_rating(self, rating: Optional[float]) -> Union[float, str]:
#         if rating is None:
#             return "Not Available"
#         return rating

#     model_config = ConfigDict(populate_by_name=True, extra='ignore')

# # --- New Models for Vendor Selection ---
# class SelectedVendorInfo(BaseModel):
#     """Represents a vendor selected by the user, to be stored in the budget plan."""
#     category_name: str = Field(..., description="The category of the selected vendor (e.g., 'venues', 'photographers')")
#     vendor_id: str = Field(..., description="The hash-based unique identifier for the selected vendor")
#     title: str = Field(..., description="The title or name of the selected vendor")
#     city: Optional[str] = Field(None, description="The city of the selected vendor (optional)")
#     rating: Optional[float] = Field(None, description="The rating of the selected vendor (optional)")
#     image_url: Optional[str] = Field(None, description="A primary image URL for the selected vendor (optional)")

# class SelectVendorRequest(BaseModel):
#     """Request body for the endpoint to select a vendor."""
#     category_name: str = Field(..., description="The category of the vendor to select (e.g., 'venues', 'photographers')")
#     vendor_id: str = Field(..., description="The ID of the vendor to select (obtained from explore-vendors endpoint)")
#     vendor_title: str = Field(..., description="The title/name of the vendor to select")
#     city: Optional[str] = Field(None, description="The city of the vendor to select (optional, for convenience)")
#     rating: Optional[float] = Field(None, description="The rating of the vendor to select (optional, for convenience)")
#     image_url: Optional[str] = Field(None, description="A primary image URL for the vendor (optional, for convenience)")
#     model_config = ConfigDict(extra='ignore')


# class ExploreVendorsResponse(BaseModel):
#     category_name: str = Field(..., description="The vendor category being explored")
#     location: str = Field(..., description="The wedding location from budget plan")
#     vendors: List[VendorItem] = Field(..., description="List of vendors for current page")
#     page: int = Field(..., description="Current page number")
#     limit: int = Field(..., description="Number of vendors per page")
#     total_vendors: int = Field(..., description="Total count of vendors matching criteria")
#     total_pages: int = Field(..., description="Total number of pages")
    
#     class Config:
#         json_schema_extra = {
#             "example": {
#                 "category_name": "venues",
#                 "location": "Bengaluru",
#                 "vendors": [
#                     {
#                         "vendor_id": "VEN_a1b2c3d4e5f6",
#                         "title": "Galaxy Club",
#                         "rating": 5.0,
#                         "image_urls": ["https://example.com/image1.jpg"],
#                         "city": "Bengaluru"
#                     },
#                     {
#                         "vendor_id": "VEN_x7y8z9m3n4p5",
#                         "title": "Royal Palace",
#                         "rating": "Not Available",
#                         "image_urls": None,
#                         "city": "Bengaluru"
#                     }
#                 ],
#                 "page": 1,
#                 "limit": 10,
#                 "total_vendors": 25,
#                 "total_pages": 3
#             }
#         } 



# weddingverse_api15/app/models/vendors.py
from pydantic import BaseModel, Field, ConfigDict, field_validator, field_serializer
from typing import List, Optional, Dict, Union
from bson import ObjectId

class VendorItem(BaseModel):
    # Required field - generated using hash-based approach for security
    vendor_id: str = Field(..., description="Unique identifier for the vendor (hash-based, not MongoDB ObjectId)")
    
    title: str = Field(..., alias="Title", description="Vendor title/name")
    
    # Rating can be None (displayed as "Not Available") or float value
    rating: Optional[float] = Field(None, alias="Rating", description="Vendor rating as a float or null for Not Available")
    
    image_urls: Optional[List[str]] = Field(None, alias="Image URLs", description="List of vendor image URLs")
    
    city: Optional[str] = Field(None, alias="City", description="Vendor city location")
    
    # Handle ObjectId conversion (for backward compatibility)
    @field_validator('vendor_id', mode='before')
    @classmethod
    def convert_objectid(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        return v
    
    # Custom serializer for rating to show "Not Available" for None values
    @field_serializer('rating')
    def serialize_rating(self, rating: Optional[float]) -> Union[float, str]:
        if rating is None:
            return "Not Available"
        return rating

    model_config = ConfigDict(populate_by_name=True, extra='ignore')

# --- New Models for Vendor Selection ---
class SelectedVendorInfo(BaseModel):
    """Represents a vendor selected by the user, to be stored in the budget plan."""
    category_name: str = Field(..., description="The category of the selected vendor (e.g., 'venues', 'photographers')")
    vendor_id: str = Field(..., description="The hash-based unique identifier for the selected vendor")
    title: str = Field(..., description="The title or name of the selected vendor")
    city: Optional[str] = Field(None, description="The city of the selected vendor (optional)")
    rating: Optional[float] = Field(None, description="The rating of the selected vendor (optional)")
    image_url: Optional[str] = Field(None, description="A primary image URL for the selected vendor (optional)")

class SelectVendorRequest(BaseModel):
    """Request body for the endpoint to select a vendor."""
    # category_name: str = Field(..., description="The category of the vendor to select (e.g., 'venues', 'photographers')")
    # ^ REMOVED: category_name will now come from the URL path.
    vendor_id: str = Field(..., description="The ID of the vendor to select (obtained from explore-vendors endpoint)")
    vendor_title: str = Field(..., description="The title/name of the vendor to select")
    city: Optional[str] = Field(None, description="The city of the vendor to select (optional, for convenience)")
    rating: Optional[float] = Field(None, description="The rating of the vendor to select (optional, for convenience)")
    image_url: Optional[str] = Field(None, description="A primary image URL for the vendor (optional, for convenience)")
    model_config = ConfigDict(extra='ignore')


class ExploreVendorsResponse(BaseModel):
    category_name: str = Field(..., description="The vendor category being explored")
    location: str = Field(..., description="The wedding location from budget plan")
    vendors: List[VendorItem] = Field(..., description="List of vendors for current page")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Number of vendors per page")
    total_vendors: int = Field(..., description="Total count of vendors matching criteria")
    total_pages: int = Field(..., description="Total number of pages")
    
    class Config:
        json_schema_extra = {
            "example": {
                "category_name": "venues",
                "location": "Bengaluru",
                "vendors": [
                    {
                        "vendor_id": "VEN_a1b2c3d4e5f6",
                        "title": "Galaxy Club",
                        "rating": 5.0,
                        "image_urls": ["https://example.com/image1.jpg"],
                        "city": "Bengaluru"
                    },
                    {
                        "vendor_id": "VEN_x7y8z9m3n4p5",
                        "title": "Royal Palace",
                        "rating": "Not Available",
                        "image_urls": None,
                        "city": "Bengaluru"
                    }
                ],
                "page": 1,
                "limit": 10,
                "total_vendors": 25,
                "total_pages": 3
            }
        }