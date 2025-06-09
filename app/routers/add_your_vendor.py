# app/routers/add_vendor_router.py (Simplified - Only POST endpoint)
from fastapi import APIRouter, HTTPException, Depends, Path

from app.models.add_your_vendor import AddVendorRequest, AddVendorResponse
from app.services.add_your_vendor import add_vendor_to_budget_category
from app.utils.logger import logger
from app.dependencies import require_jwt_auth

router = APIRouter(
    prefix="/api/v1/budget-planner/{reference_id}/category/{category_name}",
    tags=["Budget Planner - Add Vendor"],
    dependencies=[Depends(require_jwt_auth)]
)

@router.post(
    "/add-vendor",
    response_model=AddVendorResponse,
    summary="Add Vendor to Budget Category",
    description="Add a vendor to a specific budget category and update the actual cost. This is the endpoint used by the 'Add Vendor' form in the UI."
)
async def add_vendor_endpoint(
    request: AddVendorRequest,
    reference_id: str = Path(..., description="The unique reference ID of the budget plan"),
    category_name: str = Path(..., description="The category name (e.g., 'Venue', 'Caterer', 'Photography')")
):
    """
    Add a vendor to a budget category and update actual cost.
    
    This endpoint handles the complete "Add Vendor" workflow:
    1. User fills out vendor name
    2. User enters actual cost
    3. User selects payment status
    4. User clicks "Update"
    5. This endpoint updates the budget
    
    Args:
        request: Vendor information (name, cost, payment status)
        reference_id: Budget plan reference ID
        category_name: Category to update
        
    Returns:
        Success response with updated budget information
    """
    try:
        logger.info(f"Adding vendor '{request.vendor_name}' to category '{category_name}' in plan '{reference_id}'")
        
        # Validate input
        if not request.vendor_name.strip():
            raise HTTPException(
                status_code=400,
                detail="Vendor name cannot be empty."
            )
        
        if request.actual_cost < 0:
            raise HTTPException(
                status_code=400,
                detail="Actual cost cannot be negative."
            )
        
        # Add vendor using the dedicated service
        result = add_vendor_to_budget_category(
            reference_id=reference_id,
            category_name=category_name,
            vendor_name=request.vendor_name,
            actual_cost=request.actual_cost,
            payment_status=request.payment_status or "Not paid"
        )
        
        logger.info(f"Successfully added vendor '{request.vendor_name}' to {category_name}")
        
        return AddVendorResponse(
            message=f"Vendor '{request.vendor_name}' added successfully to {category_name}",
            reference_id=result["reference_id"],
            category_name=result["category_name"],
            vendor_name=result["vendor_name"],
            actual_cost=result["actual_cost"],
            estimated_amount=result["estimated_amount"],
            total_spent=result["total_spent"],
            balance=result["balance"],
            payment_status=result["payment_status"]
        )
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error adding vendor to category {category_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred while adding the vendor.")