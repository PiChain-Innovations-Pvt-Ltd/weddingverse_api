# app/models/budget.py - Fixed with datetime to string validator

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Optional
from dateutil import tz
from datetime import datetime

# --- Import the updated model ---
from app.models.vendors import SelectedVendorInfo

# Simple timestamp utility
def get_ist_timestamp() -> str:
    """Get current timestamp in IST format: YYYY-MM-DD HH:MM:SS"""
    ist = tz.gettz("Asia/Kolkata")
    return datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

def convert_datetime_to_ist_string(dt) -> str:
    """Convert datetime object to IST string format"""
    if isinstance(dt, datetime):
        # If it's already a datetime, convert to IST string
        ist = tz.gettz("Asia/Kolkata")
        if dt.tzinfo is None:
            # If naive datetime, assume UTC
            dt = dt.replace(tzinfo=tz.gettz("UTC"))
        ist_dt = dt.astimezone(ist)
        return ist_dt.strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(dt, str):
        # If it's already a string, return as-is
        return dt
    else:
        # Fallback to current timestamp
        return get_ist_timestamp()

# --- Request Model for Initial Budget Creation ---
class InitialBudgetSetupRequest(BaseModel):
    reference_id: str = Field(..., description="User's unique reference ID for the plan")
    total_budget: Optional[float] = Field(None, ge=0, description="Total budget to be divided initially (allows null, 0 or positive values)")
    guest_count: int = Field(..., gt=0, description="Estimated number of guests")
    location: str = Field(..., description="Wedding location")
    wedding_dates: str = Field(..., description="Wedding dates")
    no_of_events: int = Field(..., ge=1, description="Number of wedding events")
    model_config = ConfigDict(extra='ignore')

# --- Models for "Batch Adjust Estimates with Fixed Total" Endpoint ---
class BatchCategoryEstimateInput(BaseModel):
    category_name: str = Field(..., description="Name of the category being adjusted or added")
    new_estimate: float = Field(..., ge=0, description="The new desired estimate for this category (allows 0)")
    actual_cost: Optional[float] = Field(None, ge=0, description="Optional: The actual cost incurred for this category.")
    payment_status: Optional[str] = Field(None, description="Optional: The payment status for this category (e.g., 'Paid', 'Partially Paid', 'Not Paid').")
    model_config = ConfigDict(extra='ignore')

class BatchCategoryDeleteInput(BaseModel):
    category_name: str = Field(..., description="Name of the category to be deleted")
    model_config = ConfigDict(extra='ignore')

class BatchAdjustEstimatesFixedTotalRequest(BaseModel):
    adjustments: List[BatchCategoryEstimateInput] = Field(default=[], description="List of categories and their new estimates, actual costs, and payment statuses")
    deletions: List[BatchCategoryDeleteInput] = Field(default=[], description="List of categories to be deleted")
    new_total_budget: float = Field(default=0, description="New total budget amount. If 0 or not provided, existing budget is maintained. If > 0, budget will be updated to this value.")
    
    model_config = ConfigDict(
        extra='ignore',
        json_schema_extra={
            "example": {
                "adjustments": [
                    {
                        "category_name": "string",
                        "new_estimate": 0,
                        "actual_cost": 0,
                        "payment_status": "Not Paid"
                    }
                ],
                "deletions": [
                    {"category_name": "string"}
                ],
                "new_total_budget": 0
            }
        }
    )

# --- Shared Model for Category Breakdown in DB and API Response ---
class BudgetCategoryBreakdown(BaseModel):
    category_name: str
    percentage: float
    estimated_amount: float
    actual_cost: Optional[float] = None
    payment_status: Optional[str] = None
    is_user_set: bool = Field(default=False, description="Whether this category estimate was explicitly set by user")
    model_config = ConfigDict(extra='ignore')

# --- Database Schema Model (Fixed for backward compatibility) ---
class BudgetPlanDBSchema(BaseModel):
    reference_id: str 
    total_budget_input: float
    wedding_dates_input: str
    guest_count_input: int
    location_input: str
    no_of_events_input: int
    budget_breakdown: List[BudgetCategoryBreakdown]
    current_total_budget: float
    total_spent: float = Field(default=0.0)
    balance: float
    timestamp: str = Field(default_factory=get_ist_timestamp)  # String field
    selected_vendors: List[SelectedVendorInfo] = Field(default_factory=list, description="List of vendors selected by the user for various categories")
    
    # ✅ Validator to handle datetime objects from database
    @field_validator('timestamp', mode='before')
    @classmethod
    def convert_timestamp_to_string(cls, v):
        """Convert datetime objects to IST string format for backward compatibility"""
        return convert_datetime_to_ist_string(v)
    
    model_config = ConfigDict(extra='ignore', arbitrary_types_allowed=True)

# --- API Response Model (Simplified) ---
class BudgetPlannerAPIResponse(BaseModel):
    reference_id: str
    timestamp: str = Field(..., description="IST timestamp in YYYY-MM-DD HH:MM:SS format")
    total_budget: float
    budget_breakdown: List[BudgetCategoryBreakdown]
    spent: Optional[float] = None
    balance: Optional[float] = None
    selected_vendors: List[SelectedVendorInfo] = Field(default_factory=list, description="List of vendors selected by the user for various categories")
    
    # ✅ Validator for API response timestamp too (just in case)
    @field_validator('timestamp', mode='before')
    @classmethod
    def ensure_timestamp_is_string(cls, v):
        """Ensure timestamp is always a string"""
        return convert_datetime_to_ist_string(v)
    
    model_config = ConfigDict(extra='ignore')