# app/models/add_vendor.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from bson import ObjectId

class AddVendorRequest(BaseModel):
    """Request model for adding a vendor to a budget category."""
    vendor_name: str = Field(..., description="Name of the vendor")
    actual_cost: float = Field(..., ge=0, description="Actual cost of the vendor services")
    payment_status: Optional[str] = Field("Not paid", description="Payment status (e.g., 'Not paid', 'Paid', 'Partially paid')")
    
    class Config:
        json_schema_extra = {
            "example": {
                "vendor_name": "ABC Catering Services",
                "actual_cost": 250000,
                "payment_status": "Not paid"
            }
        }

class AddVendorResponse(BaseModel):
    """Response model for adding a vendor."""
    #success: bool = Field(True, description="Whether the operation was successful")
    message: str = Field(..., description="Success message")
    reference_id: str = Field(..., description="Budget plan reference ID")
    category_name: str = Field(..., description="Category that was updated")
    vendor_name: str = Field(..., description="Name of the added vendor")
    actual_cost: float = Field(..., description="Actual cost that was set")
    estimated_amount: float = Field(..., description="Original estimated amount for the category")
    total_spent: float = Field(..., description="Updated total spent amount")
    balance: float = Field(..., description="Updated balance")
    payment_status: str = Field(..., description="Payment status")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Vendor 'ABC Catering Services' added successfully to Caterer",
                "reference_id": "PLAN123",
                "category_name": "Caterer",
                "vendor_name": "ABC Catering Services",
                "actual_cost": 250000,
                "estimated_amount": 300000,
                "total_spent": 500000,
                "balance": 700000,
                "payment_status": "Not paid"
            }
        }