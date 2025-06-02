# # # # app/routers/vendor_selection_router.py
# # # from fastapi import APIRouter, HTTPException, Depends, Path, Body
# # # from typing import List, Optional

# # # from app.models.budget import VendorSelectionRequest, VendorRemovalRequest, VendorSelectionResponse, SelectedVendor
# # # from app.services.vendor_selection_service import (
# # #     add_selected_vendor,
# # #     remove_selected_vendor,
# # #     get_selected_vendors,
# # #     get_selected_vendor_for_category
# # # )
# # # from app.utils.logger import logger
# # # from app.dependencies import require_jwt_auth

# # # router = APIRouter(
# # #     prefix="/api/v1/budget-planner/{reference_id}/vendors", # Prefix for vendor actions related to a budget plan
# # #     tags=["Budget Planner - Vendor Selections"],
# # #     dependencies=[Depends(require_jwt_auth)]
# # # )

# # # @router.post(
# # #     "/select",
# # #     response_model=VendorSelectionResponse,
# # #     summary="Select or Update Vendor for a Category",
# # #     description="Associates a chosen vendor with a specific expense category in the budget plan. If a vendor is already selected for the category, it will be replaced."
# # # )
# # # async def endpoint_select_vendor(
# # #     reference_id: str = Path(..., description="The unique reference ID of the budget plan"),
# # #     request_body: VendorSelectionRequest = Body(..., example={
# # #         "category": "Photography",
# # #         "vendor_id": "PHOT_hash123",
# # #         "title": "Pixel Perfect Snaps",
# # #         "rating": 4.8,
# # #         "city": "Bengaluru"
# # #     })
# # # ):
# # #     try:
# # #         updated_plan = add_selected_vendor(reference_id, request_body)
# # #         return VendorSelectionResponse(
# # #             reference_id=reference_id,
# # #             selected_vendors=updated_plan.selected_vendors,
# # #             message=f"Vendor '{request_body.title}' successfully selected for category '{request_body.category}'."
# # #         )
# # #     except HTTPException as he:
# # #         raise he
# # #     except Exception as e:
# # #         logger.error(f"Error in select_vendor_endpoint for plan {reference_id}: {e}", exc_info=True)
# # #         raise HTTPException(status_code=500, detail="Internal server error during vendor selection.")

# # # @router.delete(
# # #     "/remove", # Consider making category part of the path: /remove/{category_name}
# # #     response_model=VendorSelectionResponse,
# # #     summary="Remove Selected Vendor from a Category",
# # #     description="Removes the currently selected vendor from a specific expense category in the budget plan."
# # # )
# # # async def endpoint_remove_selected_vendor(
# # #     reference_id: str = Path(..., description="The unique reference ID of the budget plan"),
# # #     request_body: VendorRemovalRequest = Body(..., example={
# # #         "category": "Photography"
# # #     })
# # # ):
# # #     try:
# # #         updated_plan = remove_selected_vendor(reference_id, request_body)
# # #         return VendorSelectionResponse(
# # #             reference_id=reference_id,
# # #             selected_vendors=updated_plan.selected_vendors,
# # #             message=f"Vendor selection for category '{request_body.category}' removed successfully."
# # #         )
# # #     except HTTPException as he:
# # #         raise he
# # #     except Exception as e:
# # #         logger.error(f"Error in remove_selected_vendor_endpoint for plan {reference_id}: {e}", exc_info=True)
# # #         raise HTTPException(status_code=500, detail="Internal server error during vendor removal.")

# # # @router.get(
# # #     "/selected",
# # #     response_model=List[SelectedVendor],
# # #     summary="Get All Selected Vendors for the Budget Plan",
# # #     description="Retrieves a list of all vendors currently selected across different categories for the specified budget plan."
# # # )
# # # async def endpoint_get_all_selected_vendors(
# # #     reference_id: str = Path(..., description="The unique reference ID of the budget plan")
# # # ):
# # #     try:
# # #         return get_selected_vendors(reference_id)
# # #     except HTTPException as he:
# # #         raise he
# # #     except Exception as e:
# # #         logger.error(f"Error in get_all_selected_vendors_endpoint for plan {reference_id}: {e}", exc_info=True)
# # #         raise HTTPException(status_code=500, detail="Internal server error retrieving selected vendors.")

# # # @router.get(
# # #     "/selected/{category_name}",
# # #     response_model=Optional[SelectedVendor], # Can be null if no vendor is selected
# # #     summary="Get Selected Vendor for a Specific Category",
# # #     description="Retrieves the details of the vendor selected for a particular category in the budget plan. Returns null if no vendor is selected for that category."
# # # )
# # # async def endpoint_get_selected_vendor_for_category(
# # #     reference_id: str = Path(..., description="The unique reference ID of the budget plan"),
# # #     category_name: str = Path(..., description="The name of the budget category")
# # # ):
# # #     try:
# # #         vendor = get_selected_vendor_for_category(reference_id, category_name)
# # #         if not vendor:
# # #             # Consistent with Optional[SelectedVendor] which becomes null in JSON
# # #             # Or you could raise a 404 if you prefer:
# # #             # raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No vendor selected for category '{category_name}'.")
# # #             return None
# # #         return vendor
# # #     except HTTPException as he:
# # #         raise he
# # #     except Exception as e:
# # #         logger.error(f"Error in get_selected_vendor_for_category_endpoint for plan {reference_id}, category {category_name}: {e}", exc_info=True)
# # #         raise HTTPException(status_code=500, detail="Internal server error retrieving selected vendor for category.") 


# # # weddingverse_api15/app/routers/vendor_selection_router.py
# # from fastapi import APIRouter, HTTPException, Depends, Path, Body
# # from app.models.budget import BudgetPlannerAPIResponse, BudgetPlanDBSchema # To return API response
# # from app.models.vendors import SelectVendorRequest # For request body
# # from app.services.vendor_selection_service import add_selected_vendor_to_plan
# # from app.utils.logger import logger
# # from app.dependencies import require_jwt_auth

# # router = APIRouter(
# #     prefix="/api/v1/budget-planner/{reference_id}",
# #     tags=["Budget Planner - Vendor Selection"],
# #     dependencies=[Depends(require_jwt_auth)]
# # )

# # @router.post(
# #     "/select-vendor",
# #     response_model=BudgetPlannerAPIResponse, # Returns the overall budget plan state
# #     summary="Add a Selected Vendor to the Budget Plan",
# #     description=(
# #         "Adds a specified vendor to the 'selected_vendors' list within the user's budget plan. "
# #         "If the exact vendor (same `vendor_id` and `category_name`) already exists, its details will be updated. "
# #         "This allows users to keep track of vendors they are interested in or have booked."
# #     )
# # )
# # async def select_vendor_endpoint(
# #     reference_id: str = Path(..., description="The unique reference ID of the budget plan"),
# #     selection_data: SelectVendorRequest = Body(
# #         ...,
# #         examples={
# #             "select_venue": {
# #                 "summary": "Select a Venue",
# #                 "value": {
# #                     "category_name": "venues",
# #                     "vendor_id": "VEN_1a2b3c4d5e6f",
# #                     "vendor_title": "The Grand Ballroom",
# #                     "city": "Bengaluru",
# #                     "rating": 4.8,
# #                     "image_url": "https://storage.googleapis.com/weddingverse-01/image/venue/wedding_bazar/AQUARIUS%20Resort%20%20Lawns/image_1.jpg"
# #                 }
# #             },
# #             "select_photographer": {
# #                 "summary": "Select a Photographer",
# #                 "value": {
# #                     "category_name": "photographers",
# #                     "vendor_id": "PHO_f1e2d3c4b5a6",
# #                     "vendor_title": "Candid Capture Studios",
# #                     "city": "Chennai",
# #                     "rating": 5.0,
# #                     "image_url": "https://storage.googleapis.com/weddingverse-01/images/venues/WedMeGood/Askon%20Banquet/image_8.jpg"
# #                 }
# #             },
# #             "update_existing_selection": {
# #                 "summary": "Update an already selected vendor's details (e.g., rating or image)",
# #                 "value": {
# #                     "category_name": "venues",
# #                     "vendor_id": "VEN_1a2b3c4d5e6f",
# #                     "vendor_title": "The Grand Ballroom", # Title must match the one used for lookup
# #                     "city": "Bengaluru",
# #                     "rating": 4.9, # Updated rating
# #                     "image_url": "https://storage.googleapis.com/weddingverse-01/images/venues/WedMeGood/Calcutta%20Boating%20%20Hotel%20Resorts/image_12.jpg" # Updated image
# #                 }
# #             },
# #             "select_another_photographer": {
# #                 "summary": "Select a second Photographer (allows multiple per category if vendor_ids differ)",
# #                 "value": {
# #                     "category_name": "photographers",
# #                     "vendor_id": "PHO_g7h8i9j0k1l2",
# #                     "vendor_title": "Elite Moments Photography",
# #                     "city": "Delhi",
# #                     "rating": 4.7
# #                 }
# #             }
# #         }
# #     )
# # ):
# #     try:
# #         updated_plan: BudgetPlanDBSchema = add_selected_vendor_to_plan(reference_id, selection_data)
        
# #         # Convert the BudgetPlanDBSchema to BudgetPlannerAPIResponse
# #         api_response = BudgetPlannerAPIResponse(
# #             reference_id=updated_plan.reference_id,
# #             total_budget=updated_plan.current_total_budget,
# #             budget_breakdown=updated_plan.budget_breakdown,
# #             spent=updated_plan.total_spent,
# #             balance=updated_plan.balance
# #             # Note: `selected_vendors` is not part of the `BudgetPlannerAPIResponse` directly.
# #             # This response model is for the budget summary. A separate endpoint could be
# #             # created to retrieve *just* the selected vendors list if needed by the frontend.
# #         )
# #         return api_response
        
# #     except HTTPException as he:
# #         raise he
# #     except Exception as e:
# #         logger.error(f"Unexpected error during vendor selection for plan {reference_id}: {e}", exc_info=True)
# #         raise HTTPException(status_code=500, detail="Internal server error during vendor selection.") 



# # weddingverse_api15/app/routers/vendor_selection_router.py
# from fastapi import APIRouter, HTTPException, Depends, Path, Body
# from app.models.budget import BudgetPlannerAPIResponse, BudgetPlanDBSchema # To return API response
# from app.models.vendors import SelectVendorRequest # For request body
# from app.services.vendor_selection_service import add_selected_vendor_to_plan
# from app.utils.logger import logger
# from app.dependencies import require_jwt_auth

# router = APIRouter(
#     # Changed prefix to include category_name
#     prefix="/api/v1/budget-planner/{reference_id}/category/{category_name}",
#     tags=["Budget Planner - Vendor Selection"],
#     dependencies=[Depends(require_jwt_auth)]
# )

# @router.post(
#     # Changed path to just /select-vendor
#     "/select-vendor",
#     response_model=BudgetPlannerAPIResponse, # Returns the overall budget plan state
#     summary="Add a Selected Vendor to the Budget Plan",
#     description=(
#         "Adds a specified vendor to the 'selected_vendors' list within the user's budget plan for a given category. "
#         "If the exact vendor (same `vendor_id` within the `category_name`) already exists, its details will be updated. "
#         "This allows users to keep track of vendors they are interested in or have booked."
#     )
# )
# async def select_vendor_endpoint(
#     reference_id: str = Path(..., description="The unique reference ID of the budget plan"),
#     # Added category_name as a Path parameter
#     category_name: str = Path(..., description="The category of the vendor being selected (e.g., 'venues', 'photographers')"),
#     selection_data: SelectVendorRequest = Body(
#         ...,
#         examples={
#             "select_venue": {
#                 "summary": "Select a Venue",
#                 "value": {
#                     # "category_name": "venues", # REMOVED from body example
#                     "vendor_id": "VEN_1a2b3c4d5e6f",
#                     "vendor_title": "The Grand Ballroom",
#                     "city": "Bengaluru",
#                     "rating": 4.8,
#                     "image_url": "https://storage.googleapis.com/weddingverse-01/image/venue/wedding_bazar/AQUARIUS%20Resort%20%20Lawns/image_1.jpg"
#                 }
#             },
#             "select_photographer": {
#                 "summary": "Select a Photographer",
#                 "value": {
#                     # "category_name": "photographers", # REMOVED from body example
#                     "vendor_id": "PHO_f1e2d3c4b5a6",
#                     "vendor_title": "Candid Capture Studios",
#                     "city": "Chennai",
#                     "rating": 5.0,
#                     "image_url": "https://storage.googleapis.com/weddingverse-01/images/venues/WedMeGood/Askon%20Banquet/image_8.jpg"
#                 }
#             },
#             "update_existing_selection": {
#                 "summary": "Update an already selected vendor's details (e.g., rating or image)",
#                 "value": {
#                     # "category_name": "venues", # REMOVED from body example
#                     "vendor_id": "VEN_1a2b3c4d5e6f",
#                     "vendor_title": "The Grand Ballroom", # Title must match the one used for lookup
#                     "city": "Bengaluru",
#                     "rating": 4.9, # Updated rating
#                     "image_url": "https://storage.googleapis.com/weddingverse-01/images/venues/WedMeGood/Calcutta%20Boating%20%20Hotel%20Resorts/image_12.jpg" # Updated image
#                 }
#             },
#             "select_another_photographer": {
#                 "summary": "Select a second Photographer (allows multiple per category if vendor_ids differ)",
#                 "value": {
#                     # "category_name": "photographers", # REMOVED from body example
#                     "vendor_id": "PHO_g7h8i9j0k1l2",
#                     "vendor_title": "Elite Moments Photography",
#                     "city": "Delhi",
#                     "rating": 4.7
#                 }
#             }
#         }
#     )
# ):
#     try:
#         # Pass category_name from path to the service
#         updated_plan: BudgetPlanDBSchema = add_selected_vendor_to_plan(reference_id, category_name, selection_data)
        
#         api_response = BudgetPlannerAPIResponse(
#             reference_id=updated_plan.reference_id,
#             total_budget=updated_plan.current_total_budget,
#             budget_breakdown=updated_plan.budget_breakdown,
#             spent=updated_plan.total_spent,
#             balance=updated_plan.balance
#         )
#         return api_response
        
#     except HTTPException as he:
#         raise he
#     except Exception as e:
#         logger.error(f"Unexpected error during vendor selection for plan {reference_id}: {e}", exc_info=True)
#         raise HTTPException(status_code=500, detail="Internal server error during vendor selection.") 


# weddingverse_api15/app/routers/vendor_selection_router.py
from fastapi import APIRouter, HTTPException, Depends, Path, Body
from app.models.budget import BudgetPlannerAPIResponse, BudgetPlanDBSchema # To return API response
from app.models.vendors import SelectVendorRequest # For request body
from app.services.vendor_selection_service import add_selected_vendor_to_plan
from app.utils.logger import logger
from app.dependencies import require_jwt_auth

router = APIRouter(
    # Changed prefix to include category_name
    prefix="/api/v1/budget-planner/{reference_id}/category/{category_name}",
    tags=["Budget Planner - Vendor Selection"],
    dependencies=[Depends(require_jwt_auth)]
)

@router.post(
    # Changed path to just /select-vendor
    "/select-vendor",
    response_model=BudgetPlannerAPIResponse, # Returns the overall budget plan state
    summary="Add a Selected Vendor to the Budget Plan",
    description=(
        "Adds a specified vendor to the 'selected_vendors' list within the user's budget plan for a given category. "
        "If the exact vendor (same `vendor_id` within the `category_name`) already exists, its details will be updated. "
        "This allows users to keep track of vendors they are interested in or have booked."
    )
)
async def select_vendor_endpoint(
    reference_id: str = Path(..., description="The unique reference ID of the budget plan"),
    # Added category_name as a Path parameter
    category_name: str = Path(..., description="The category of the vendor being selected (e.g., 'venues', 'photographers')"),
    selection_data: SelectVendorRequest = Body(
        ...,
        examples={
            "select_venue": {
                "summary": "Select a Venue",
                "value": {
                    # "category_name": "venues", # REMOVED from body example
                    "vendor_id": "VEN_1a2b3c4d5e6f",
                    "vendor_title": "The Grand Ballroom",
                    "city": "Bengaluru",
                    "rating": 4.8,
                    "image_url": "https://storage.googleapis.com/weddingverse-01/image/venue/wedding_bazar/AQUARIUS%20Resort%20%20Lawns/image_1.jpg"
                }
            },
            "select_photographer": {
                "summary": "Select a Photographer",
                "value": {
                    # "category_name": "photographers", # REMOVED from body example
                    "vendor_id": "PHO_f1e2d3c4b5a6",
                    "vendor_title": "Candid Capture Studios",
                    "city": "Chennai",
                    "rating": 5.0,
                    "image_url": "https://storage.googleapis.com/weddingverse-01/images/venues/WedMeGood/Askon%20Banquet/image_8.jpg"
                }
            },
            "update_existing_selection": {
                "summary": "Update an already selected vendor's details (e.g., rating or image)",
                "value": {
                    # "category_name": "venues", # REMOVED from body example
                    "vendor_id": "VEN_1a2b3c4d5e6f",
                    "vendor_title": "The Grand Ballroom", # Title must match the one used for lookup
                    "city": "Bengaluru",
                    "rating": 4.9, # Updated rating
                    "image_url": "https://storage.googleapis.com/weddingverse-01/images/venues/WedMeGood/Calcutta%20Boating%20%20Hotel%20Resorts/image_12.jpg" # Updated image
                }
            },
            "select_another_photographer": {
                "summary": "Select a second Photographer (allows multiple per category if vendor_ids differ)",
                "value": {
                    # "category_name": "photographers", # REMOVED from body example
                    "vendor_id": "PHO_g7h8i9j0k1l2",
                    "vendor_title": "Elite Moments Photography",
                    "city": "Delhi",
                    "rating": 4.7
                }
            }
        }
    )
):
    try:
        # Pass category_name from path to the service
        updated_plan: BudgetPlanDBSchema = add_selected_vendor_to_plan(reference_id, category_name, selection_data)
        
        # Construct the API response, now including selected_vendors
        api_response = BudgetPlannerAPIResponse(
            reference_id=updated_plan.reference_id,
            total_budget=updated_plan.current_total_budget,
            budget_breakdown=updated_plan.budget_breakdown,
            spent=updated_plan.total_spent,
            balance=updated_plan.balance,
            selected_vendors=updated_plan.selected_vendors # ADDED: Pass the selected_vendors
        )
        return api_response
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Unexpected error during vendor selection for plan {reference_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during vendor selection.")