# # # weddingverse_api15/app/models/vendors.py
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

# # # --- Model for Selected Vendor Info (stored in budget plan) ---
# # class SelectedVendorInfo(BaseModel):
# #     """Represents a vendor selected by the user, to be stored in the budget plan."""
# #     category_name: str = Field(..., description="The category of the selected vendor (e.g., 'venues', 'photographers')")
# #     vendor_id: str = Field(..., description="The MongoDB ObjectId of the selected vendor")
# #     title: str = Field(..., description="The title or name of the selected vendor")
# #     city: Optional[str] = Field(None, description="The city of the selected vendor (optional)")
# #     rating: Optional[float] = Field(None, description="The rating of the selected vendor (optional)")
# #     image_urls: Optional[List[str]] = Field(None, description="List of image URLs for the selected vendor (optional)")

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
# #                 "limit": 16,
# #                 "total_vendors": 25,
# #                 "total_pages": 3
# #             }
# #         } 


# # weddingverse_api15/app/models/vendors.py
# from pydantic import BaseModel, Field, ConfigDict, field_validator, field_serializer
# from typing import List, Optional, Dict, Union, Any
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

# # NEW: Detailed vendor information model
# class VendorDetails(BaseModel):
#     """Complete vendor information for detailed view/messaging."""
#     vendor_id: str = Field(..., description="Unique identifier for the vendor")
#     category_name: str = Field(..., description="Category/collection name this vendor belongs to")
#     title: str = Field(..., description="Vendor title/name")
#     rating: Optional[float] = Field(None, description="Vendor rating")
#     city: Optional[str] = Field(None, description="Vendor city location")
#     image_urls: Optional[List[str]] = Field(None, description="List of vendor image URLs")
    
#     # Additional fields that might be present in the full document
#     description: Optional[str] = Field(None, description="Vendor description")
#     contact_info: Optional[Dict[str, Any]] = Field(None, description="Contact information")
#     price_range: Optional[str] = Field(None, description="Price range information")
#     services: Optional[List[str]] = Field(None, description="List of services offered")
#     availability: Optional[Dict[str, Any]] = Field(None, description="Availability information")
#     location_details: Optional[Dict[str, Any]] = Field(None, description="Detailed location information")
#     portfolio: Optional[List[str]] = Field(None, description="Portfolio images")
#     reviews: Optional[List[Dict[str, Any]]] = Field(None, description="Customer reviews")
#     amenities: Optional[List[str]] = Field(None, description="Available amenities")
#     capacity: Optional[Dict[str, Any]] = Field(None, description="Venue capacity details")
    
#     # Store any additional fields that might be collection-specific
#     additional_fields: Optional[Dict[str, Any]] = Field(None, description="Any additional collection-specific fields")
    
#     @field_validator('vendor_id', mode='before')
#     @classmethod
#     def convert_objectid(cls, v):
#         if isinstance(v, ObjectId):
#             return str(v)
#         return v
    
#     @field_serializer('rating')
#     def serialize_rating(self, rating: Optional[float]) -> Union[float, str]:
#         if rating is None:
#             return "Not Available"
#         return rating

#     model_config = ConfigDict(populate_by_name=True, extra='ignore')

# # NEW: Response model for vendor details
# class VendorDetailsResponse(BaseModel):
#     """Response model for detailed vendor information."""
#     success: bool = Field(True, description="Whether the request was successful")
#     vendor: VendorDetails = Field(..., description="Complete vendor information")
    
#     class Config:
#         json_schema_extra = {
#             "example": {
#                 "success": True,
#                 "vendor": {
#                     "vendor_id": "507f1f77bcf86cd799439011",
#                     "category_name": "venues",
#                     "title": "Timeless Moments Studio",
#                     "rating": 4.5,
#                     "city": "Bengaluru",
#                     "image_urls": ["https://example.com/image1.jpg", "https://example.com/image2.jpg"],
#                     "description": "Premium wedding venue with modern amenities",
#                     "contact_info": {
#                         "phone": "+91-9876543210",
#                         "email": "contact@timelessmoments.com",
#                         "website": "https://timelessmoments.com"
#                     },
#                     "price_range": "₹2,00,000 - ₹5,00,000",
#                     "services": ["Wedding Ceremonies", "Reception", "Photography", "Catering"],
#                     "amenities": ["Air Conditioning", "Parking", "Sound System", "Lighting"],
#                     "capacity": {
#                         "min_guests": 100,
#                         "max_guests": 500
#                     }
#                 }
#             }
#         }

# # --- Model for Selected Vendor Info (stored in budget plan) ---
# class SelectedVendorInfo(BaseModel):
#     """Represents a vendor selected by the user, to be stored in the budget plan."""
#     category_name: str = Field(..., description="The category of the selected vendor (e.g., 'venues', 'photographers')")
#     vendor_id: str = Field(..., description="The MongoDB ObjectId of the selected vendor")
#     title: str = Field(..., description="The title or name of the selected vendor")
#     city: Optional[str] = Field(None, description="The city of the selected vendor (optional)")
#     rating: Optional[float] = Field(None, description="The rating of the selected vendor (optional)")
#     image_urls: Optional[List[str]] = Field(None, description="List of image URLs for the selected vendor (optional)")

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
#                 "limit": 16,
#                 "total_vendors": 25,
#                 "total_pages": 3
#             }
#         } 



# weddingverse_api15/app/models/vendors.py
from pydantic import BaseModel, Field, ConfigDict, field_validator, field_serializer
from typing import List, Optional, Dict, Union, Any
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

# NEW: Detailed vendor information model (Flexible for any DB structure)
class VendorDetails(BaseModel):
    """Complete vendor information for detailed view/messaging. Works with any database structure."""
    vendor_id: str = Field(..., description="Unique identifier for the vendor (MongoDB ObjectId)")
    category_name: str = Field(..., description="Category/collection name this vendor belongs to")
    
    # Basic fields (extracted if available, with defaults)
    title: str = Field(default="Unknown", description="Vendor title/name")
    rating: Optional[float] = Field(None, description="Vendor rating")
    city: Optional[str] = Field(None, description="Vendor city location")
    image_urls: Optional[List[str]] = Field(None, description="List of vendor image URLs")
    
    # All other fields from the MongoDB document
    additional_fields: Optional[Dict[str, Any]] = Field(None, description="All additional fields from the vendor document")
    
    @field_validator('vendor_id', mode='before')
    @classmethod
    def convert_objectid(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        return v
    
    @field_serializer('rating')
    def serialize_rating(self, rating: Optional[float]) -> Union[float, str]:
        if rating is None:
            return "Not Available"
        return rating

    model_config = ConfigDict(populate_by_name=True, extra='ignore')

# NEW: Response model for vendor details
class VendorDetailsResponse(BaseModel):
    """Response model for detailed vendor information."""
    #success: bool = Field(True, description="Whether the request was successful")
    vendor: VendorDetails = Field(..., description="Complete vendor information")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "vendor": {
                    "vendor_id": "507f1f77bcf86cd799439011",
                    "category_name": "venues",
                    "title": "Timeless Moments Studio",
                    "rating": 4.5,
                    "city": "Bengaluru",
                    "image_urls": ["https://example.com/image1.jpg", "https://example.com/image2.jpg"],
                    "description": "Premium wedding venue with modern amenities",
                    "contact_info": {
                        "phone": "+91-9876543210",
                        "email": "contact@timelessmoments.com",
                        "website": "https://timelessmoments.com"
                    },
                    "price_range": "₹2,00,000 - ₹5,00,000",
                    "services": ["Wedding Ceremonies", "Reception", "Photography", "Catering"],
                    "amenities": ["Air Conditioning", "Parking", "Sound System", "Lighting"],
                    "capacity": {
                        "min_guests": 100,
                        "max_guests": 500
                    }
                }
            }
        }

# --- Model for Selected Vendor Info (stored in budget plan) ---
class SelectedVendorInfo(BaseModel):
    """Represents a vendor selected by the user, to be stored in the budget plan."""
    category_name: str = Field(..., description="The category of the selected vendor (e.g., 'venues', 'photographers')")
    vendor_id: str = Field(..., description="The MongoDB ObjectId of the selected vendor")
    title: str = Field(..., description="The title or name of the selected vendor")
    city: Optional[str] = Field(None, description="The city of the selected vendor (optional)")
    rating: Optional[float] = Field(None, description="The rating of the selected vendor (optional)")
    image_urls: Optional[List[str]] = Field(None, description="List of image URLs for the selected vendor (optional)")

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
                "limit": 16,
                "total_vendors": 25,
                "total_pages": 3
            }
        }