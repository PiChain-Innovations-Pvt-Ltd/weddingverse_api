# # # app/models/budget.py
# # from pydantic import BaseModel, Field, ConfigDict, field_validator
# # from typing import List, Optional
# # from datetime import datetime, timezone

# # # --- Request Model for Initial Budget Creation ---
# # class InitialBudgetSetupRequest(BaseModel):
# #     reference_id: str = Field(..., description="User's unique reference ID for the plan")
# #     total_budget: Optional[float] = Field(None, ge=0, description="Total budget to be divided initially (allows null, 0 or positive values)")
# #     guest_count: int = Field(..., gt=0, description="Estimated number of guests")
# #     location: str = Field(..., description="Wedding location")
# #     wedding_dates: str = Field(..., description="Wedding dates")
# #     no_of_events: int = Field(..., ge=1, description="Number of wedding events")
# #     model_config = ConfigDict(extra='ignore')


# # # --- Models for "Batch Adjust Estimates" Endpoint ---
# # class BatchCategoryEstimateInput(BaseModel):
# #     category_name: str = Field(..., description="Name of the category being adjusted or added")
# #     new_estimate: float = Field(..., ge=0, description="The new desired estimate for this category (allows 0)")
# #     actual_cost: Optional[float] = Field(None, ge=0, description="Optional: The actual cost incurred for this category.")
# #     payment_status: Optional[str] = Field(None, description="Optional: The payment status for this category (e.g., 'Paid', 'Partially Paid', 'Not Paid').")
# #     model_config = ConfigDict(extra='ignore')

# # class BatchCategoryDeleteInput(BaseModel):
# #     category_name: str = Field(..., description="Name of the category to be deleted")
# #     model_config = ConfigDict(extra='ignore')

# # class BatchAdjustEstimatesFixedTotalRequest(BaseModel): # Name kept for consistency with existing router
# #     adjustments: List[BatchCategoryEstimateInput] = Field(default=[], description="List of categories and their new estimates, actual costs, and payment statuses")
# #     deletions: List[BatchCategoryDeleteInput] = Field(default=[], description="List of categories to be deleted")
# #     new_total_budget: float = Field(default=0, description="New total budget amount. If 0 or not provided, existing budget is maintained. If > 0, budget will be updated to this value.")
    
# #     model_config = ConfigDict(
# #         extra='ignore',
# #         json_schema_extra={
# #             "example": {
# #                 "adjustments": [
# #                     {"category_name": "Venue", "new_estimate": 50000, "actual_cost": 48000, "payment_status": "Paid"}
# #                 ],
# #                 "deletions": [
# #                     {"category_name": "Old Decor"}
# #                 ],
# #                 "new_total_budget": 200000
# #             }
# #         }
# #     )

# # # --- Shared Model for Category Breakdown in DB and API Response ---
# # class BudgetCategoryBreakdown(BaseModel):
# #     category_name: str
# #     percentage: float
# #     estimated_amount: float
# #     actual_cost: Optional[float] = None
# #     payment_status: Optional[str] = None
# #     model_config = ConfigDict(extra='ignore')

# # # --- NEW: Selected Vendor Models ---
# # class SelectedVendor(BaseModel):
# #     category: str = Field(..., description="Vendor category (e.g., 'Venue', 'DJ', 'Photography')")
# #     vendor_id: str = Field(..., description="Unique identifier for the selected vendor (from vendor discovery)")
# #     title: str = Field(..., description="Vendor name/title")
# #     rating: Optional[float] = Field(None, description="Vendor rating (can be None)")
# #     city: Optional[str] = Field(None, description="Vendor location/city")
# #     model_config = ConfigDict(extra='ignore')

# # class VendorSelectionRequest(BaseModel):
# #     category: str = Field(..., description="The budget category this vendor is for")
# #     vendor_id: str = Field(..., description="The unique ID of the vendor being selected")
# #     title: str = Field(..., description="The title/name of the vendor")
# #     rating: Optional[float] = Field(None, description="The rating of the vendor, if available")
# #     city: Optional[str] = Field(None, description="The city of the vendor, if available")
# #     model_config = ConfigDict(extra='ignore')

# # class VendorRemovalRequest(BaseModel):
# #     category: str = Field(..., description="The budget category from which to remove the selected vendor")
# #     model_config = ConfigDict(extra='ignore')

# # class VendorSelectionResponse(BaseModel):
# #     reference_id: str
# #     selected_vendors: List[SelectedVendor]
# #     message: str
# #     model_config = ConfigDict(extra='ignore')

# # # --- Database Schema Model (Updated) ---
# # class BudgetPlanDBSchema(BaseModel):
# #     reference_id: str 
# #     total_budget_input: float
# #     wedding_dates_input: str
# #     guest_count_input: int
# #     location_input: str
# #     no_of_events_input: int
# #     budget_breakdown: List[BudgetCategoryBreakdown]
# #     current_total_budget: float
# #     total_spent: float = Field(default=0.0)
# #     balance: float
# #     selected_vendors: List[SelectedVendor] = Field(default=[])
# #     timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
# #     model_config = ConfigDict(extra='ignore', arbitrary_types_allowed=True) # populate_by_name=True removed as we are not using _id alias here

# # # --- API Response Model (Shared by all budget features) ---
# # class BudgetPlannerAPIResponse(BaseModel):
# #     reference_id: str
# #     timestamp: datetime # This field is required
# #     total_budget: float # Maps to current_total_budget
# #     budget_breakdown: List[BudgetCategoryBreakdown]
# #     spent: Optional[float] = None
# #     balance: Optional[float] = None
# #     model_config = ConfigDict(extra='ignore') 


# # weddingverse_api15/app/models/budget.py
# from pydantic import BaseModel, Field, ConfigDict, field_validator
# from typing import List, Optional
# from datetime import datetime, timezone

# # --- Import the new model ---
# from app.models.vendors import SelectedVendorInfo

# # --- Request Model for Initial Budget Creation ---
# class InitialBudgetSetupRequest(BaseModel):
#     reference_id: str = Field(..., description="User's unique reference ID for the plan")
#     total_budget: Optional[float] = Field(None, ge=0, description="Total budget to be divided initially (allows null, 0 or positive values)")
#     guest_count: int = Field(..., gt=0, description="Estimated number of guests")
#     location: str = Field(..., description="Wedding location")
#     wedding_dates: str = Field(..., description="Wedding dates")
#     no_of_events: int = Field(..., ge=1, description="Number of wedding events")
#     model_config = ConfigDict(extra='ignore')


# # --- Models for "Batch Adjust Estimates with Fixed Total" Endpoint ---
# class BatchCategoryEstimateInput(BaseModel):
#     category_name: str = Field(..., description="Name of the category being adjusted or added")
#     new_estimate: float = Field(..., ge=0, description="The new desired estimate for this category (allows 0)")
#     actual_cost: Optional[float] = Field(None, ge=0, description="Optional: The actual cost incurred for this category.")
#     payment_status: Optional[str] = Field(None, description="Optional: The payment status for this category (e.g., 'Paid', 'Partially Paid', 'Not Paid').")
#     model_config = ConfigDict(extra='ignore')

# class BatchCategoryDeleteInput(BaseModel):
#     category_name: str = Field(..., description="Name of the category to be deleted")
#     model_config = ConfigDict(extra='ignore')

# class BatchAdjustEstimatesFixedTotalRequest(BaseModel):
#     adjustments: List[BatchCategoryEstimateInput] = Field(default=[], description="List of categories and their new estimates, actual costs, and payment statuses")
#     deletions: List[BatchCategoryDeleteInput] = Field(default=[], description="List of categories to be deleted")
#     new_total_budget: float = Field(default=0, description="New total budget amount. If 0 or not provided, existing budget is maintained. If > 0, budget will be updated to this value.")
    
#     model_config = ConfigDict(
#         extra='ignore',
#         json_schema_extra={
#             "example": { # Changed from "examples" to "example" for a single, simpler example
#                 "adjustments": [
#                     {
#                         "category_name": "string",
#                         "new_estimate": 0, # Changed from 'estimate' to 'new_estimate'
#                         "actual_cost": 0, # Added actual_cost
#                         "payment_status": "Not Paid" # Added payment_status
#                     }
#                 ],
#                 "deletions": [
#                     {"category_name": "string"}
#                 ],
#                 "new_total_budget": 0
#             }
#         }
#     )

# # --- Shared Model for Category Breakdown in DB and API Response ---
# class BudgetCategoryBreakdown(BaseModel):
#     category_name: str
#     percentage: float
#     estimated_amount: float
#     actual_cost: Optional[float] = None # Actual cost recorded for this individual category
#     payment_status: Optional[str] = None # E.g., "Not Paid", "Partially Paid", "Paid"
#     model_config = ConfigDict(extra='ignore')

# # --- Database Schema Model (Shared) ---
# class BudgetPlanDBSchema(BaseModel):
#     reference_id: str 
#     total_budget_input: float
#     wedding_dates_input: str
#     guest_count_input: int
#     location_input: str
#     no_of_events_input: int
#     budget_breakdown: List[BudgetCategoryBreakdown]
#     current_total_budget: float # The effective total budget of the plan, can change from total_budget_input
#     total_spent: float = Field(default=0.0) # Total *spent* across all categories (sum of all actual_cost)
#     balance: float # current_total_budget - total_spent
#     timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
#     # --- New field for selected vendors ---
#     selected_vendors: List[SelectedVendorInfo] = Field(default_factory=list, description="List of vendors selected by the user for various categories")
#     model_config = ConfigDict(extra='ignore', arbitrary_types_allowed=True)

# # --- API Response Model (Shared by all budget features) ---
# class BudgetPlannerAPIResponse(BaseModel):
#     reference_id: str
#     timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
#     total_budget: float # Maps to current_total_budget
#     budget_breakdown: List[BudgetCategoryBreakdown]
#     spent: Optional[float] = None # Total *spent* across all categories (for API response)
#     balance: Optional[float] = None # current_total_budget - spent (for API response)
#     model_config = ConfigDict(extra='ignore') 



# weddingverse_api15/app/models/budget.py
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Optional
from datetime import datetime, timezone

# --- Import the new model ---
from app.models.vendors import SelectedVendorInfo

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
            "example": { # Changed from "examples" to "example" for a single, simpler example
                "adjustments": [
                    {
                        "category_name": "string",
                        "new_estimate": 0, # Changed from 'estimate' to 'new_estimate'
                        "actual_cost": 0, # Added actual_cost
                        "payment_status": "Not Paid" # Added payment_status
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
    actual_cost: Optional[float] = None # Actual cost recorded for this individual category
    payment_status: Optional[str] = None # E.g., "Not Paid", "Partially Paid", "Paid"
    model_config = ConfigDict(extra='ignore')

# --- Database Schema Model (Shared) ---
class BudgetPlanDBSchema(BaseModel):
    reference_id: str 
    total_budget_input: float
    wedding_dates_input: str
    guest_count_input: int
    location_input: str
    no_of_events_input: int
    budget_breakdown: List[BudgetCategoryBreakdown]
    current_total_budget: float # The effective total budget of the plan, can change from total_budget_input
    total_spent: float = Field(default=0.0) # Total *spent* across all categories (sum of all actual_cost)
    balance: float # current_total_budget - total_spent
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # --- New field for selected vendors ---
    selected_vendors: List[SelectedVendorInfo] = Field(default_factory=list, description="List of vendors selected by the user for various categories")
    model_config = ConfigDict(extra='ignore', arbitrary_types_allowed=True)

# --- API Response Model (Shared by all budget features) ---
class BudgetPlannerAPIResponse(BaseModel):
    reference_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_budget: float # Maps to current_total_budget
    budget_breakdown: List[BudgetCategoryBreakdown]
    spent: Optional[float] = None # Total *spent* across all categories (for API response)
    balance: Optional[float] = None # current_total_budget - spent (for API response)
    # ADDED: Include selected_vendors in the API response
    selected_vendors: List[SelectedVendorInfo] = Field(default_factory=list, description="List of vendors selected by the user for various categories")
    model_config = ConfigDict(extra='ignore')