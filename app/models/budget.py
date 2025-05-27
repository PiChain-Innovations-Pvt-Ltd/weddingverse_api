# app/models/budget.py
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Optional
from datetime import datetime, timezone

# --- Request Model for Initial Budget Creation ---
class InitialBudgetSetupRequest(BaseModel):
    reference_id: str = Field(..., description="User's unique reference ID for the plan")
    total_budget: float = Field(..., gt=0, description="Total budget to be divided initially")
    guest_count: int = Field(..., gt=0, description="Estimated number of guests")
    location: str = Field(..., description="Wedding location")
    wedding_dates: str = Field(..., description="Wedding dates")
    no_of_events: int = Field(..., ge=1, description="Number of wedding events")
    model_config = ConfigDict(extra='ignore')


# --- Models for "Batch Adjust Estimates with Fixed Total" Endpoint ---
class BatchCategoryEstimateInput(BaseModel):
    category_name: str = Field(..., description="Name of the category being adjusted")
    new_estimate: float = Field(..., ge=0, description="The new desired estimate for this category (ge=0 allows 0)")
    model_config = ConfigDict(extra='ignore')

class BatchAdjustEstimatesFixedTotalRequest(BaseModel):
    adjustments: List[BatchCategoryEstimateInput] = Field(..., min_length=1, description="List of categories and their new estimates")
    model_config = ConfigDict(extra='ignore')

# --- Shared Model for Category Breakdown in DB and API Response ---
class BudgetCategoryBreakdown(BaseModel):
    category_name: str
    percentage: float
    estimated_amount: float
    model_config = ConfigDict(extra='ignore')

# --- Database Schema Model (Shared) ---
class BudgetPlanDBSchema(BaseModel):
    reference_id: str = Field(alias="_id")
    total_budget_input: float
    wedding_dates_input: str
    guest_count_input: int
    location_input: str
    no_of_events_input: int
    budget_breakdown: List[BudgetCategoryBreakdown]
    current_total_budget: float
    total_spent: float = Field(default=0.0)
    balance: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_config = ConfigDict(populate_by_name=True, extra='ignore', arbitrary_types_allowed=True)

# --- API Response Model (Shared by all budget features) ---
class BudgetPlannerAPIResponse(BaseModel):
    reference_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_budget: float # Maps to current_total_budget
    budget_breakdown: List[BudgetCategoryBreakdown]
    spent: Optional[float] = None
    balance: Optional[float] = None
    model_config = ConfigDict(extra='ignore')

class BatchAdjustEstimatesFixedTotalRequest(BaseModel):
    adjustments: List[BatchCategoryEstimateInput] = Field(..., min_length=1, description="List of categories and their new estimates")
    new_total_budget: float = Field(default=0, description="New total budget amount. If 0 or not provided, existing budget is maintained. If > 0, budget will be updated to this value.")
    model_config = ConfigDict(extra='ignore')