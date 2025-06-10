# app/services/add_your_vendor.py - Simplified with IST timestamps
from typing import Dict, Any
from fastapi import HTTPException, status
from dateutil import tz
from datetime import datetime

from app.models.budget import BudgetPlanDBSchema
from app.models.vendors import SelectedVendorInfo
from app.services.mongo_service import db
from app.utils.logger import logger
from app.config import settings

BUDGET_PLANS_COLLECTION = settings.BUDGET_PLANS_COLLECTION

# Simple timestamp utility
def get_ist_timestamp() -> str:
    """Get current timestamp in IST format: YYYY-MM-DD HH:MM:SS"""
    ist = tz.gettz("Asia/Kolkata")
    return datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

# # Mapping from budget category names to vendor collection names
# BUDGET_CATEGORY_TO_VENDOR_COLLECTION_MAP = {
#     "Venue": "venues",
#     "Caterer": "catering", 
#     "Photography": "photographers",
#     "Makeup": "makeups",
#     "DJ": "djs",
#     "Decor": "decors",
#     "Mehendi": "mehendi",
#     "Bridal Wear": "bridal_wear",
#     "Wedding Invitations": "weddingInvitations",
#     "Honeymoon": "honeymoon",
#     "Car": "car",
#     "Astrology": "astro",
#     "Jewellery": "jewellery",
#     "Wedding Planner": "wedding_planner",
# }

def generate_user_vendor_id(vendor_name: str, category_name: str) -> str:
    """Generate a unique ID for user-added vendors."""
    import hashlib
    name_hash = hashlib.md5(f"{vendor_name}_{category_name}".encode()).hexdigest()[:8]
    return f"USER_VENDOR_{category_name.upper()}_{name_hash}"

def add_vendor_to_budget_category(
    reference_id: str,
    category_name: str,
    vendor_name: str,
    actual_cost: float,
    payment_status: str = "Not paid"
) -> Dict[str, Any]:
    """
    Add a vendor to a budget category with simplified IST timestamp handling.
    """
    logger.info(f"[ADD_VENDOR] Adding vendor '{vendor_name}' to category '{category_name}' in plan '{reference_id}' with cost ₹{actual_cost}")
    
    try:
        # Fetch the current budget plan
        plan_dict = db[BUDGET_PLANS_COLLECTION].find_one({"reference_id": reference_id})
        if not plan_dict:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Budget plan '{reference_id}' not found."
            )
        
        # Validate the budget plan
        try:
            budget_plan = BudgetPlanDBSchema.model_validate(plan_dict)
        except Exception as e:
            logger.error(f"Budget plan validation error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error reading budget plan data."
            )
        
        # Find and update the category in the budget breakdown
        category_found = False
        category_info = {}
        
        for category in budget_plan.budget_breakdown:
            if category.category_name.lower() == category_name.lower():
                # Update the actual cost and payment status for this category
                category.actual_cost = actual_cost
                category.payment_status = payment_status
                
                # Store category info for response
                category_info = {
                    "category_name": category.category_name,
                    "estimated_amount": category.estimated_amount,
                    "actual_cost": actual_cost,
                    "percentage": category.percentage,
                    "payment_status": payment_status
                }
                
                category_found = True
                logger.info(f"[ADD_VENDOR] Updated category '{category_name}': actual_cost={actual_cost}, payment_status={payment_status}")
                break
        
        if not category_found:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Category '{category_name}' not found in budget plan."
            )
        
        # Add vendor to selected_vendors list
        user_vendor_id = generate_user_vendor_id(vendor_name, category_name)
        vendor_collection_name = category_name
        
        user_selected_vendor = SelectedVendorInfo(
            category_name=vendor_collection_name,
            vendor_id=user_vendor_id,
            title=vendor_name,
            city=None,
            rating=None,
            image_urls=None
        )
        
        # Check if vendor already exists and update/add accordingly
        existing_vendor_index = -1
        for i, sv in enumerate(budget_plan.selected_vendors):
            if sv.category_name == vendor_collection_name and sv.vendor_id == user_vendor_id:
                existing_vendor_index = i
                break
        
        if existing_vendor_index != -1:
            budget_plan.selected_vendors[existing_vendor_index] = user_selected_vendor
            logger.info(f"[ADD_VENDOR] Updated existing user vendor '{vendor_name}' in selected_vendors")
        else:
            budget_plan.selected_vendors.append(user_selected_vendor)
            logger.info(f"[ADD_VENDOR] Added new user vendor '{vendor_name}' to selected_vendors")
        
        # Recalculate totals
        total_spent = sum(
            category.actual_cost for category in budget_plan.budget_breakdown 
            if category.actual_cost is not None
        )
        
        budget_plan.total_spent = round(total_spent, 2)
        budget_plan.balance = round(budget_plan.current_total_budget - budget_plan.total_spent, 2)
        
        # ✅ Simple timestamp update
        budget_plan.timestamp = get_ist_timestamp()
        logger.info(f"[ADD_VENDOR] Updated timestamp: {budget_plan.timestamp}")
        
        # Update the budget plan in database
        update_data = budget_plan.model_dump()
        
        result = db[BUDGET_PLANS_COLLECTION].update_one(
            {"reference_id": reference_id},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update budget plan."
            )
        
        logger.info(f"[ADD_VENDOR] Successfully updated budget plan {reference_id} with vendor selection")
        
        # Return the updated information
        return {
            "reference_id": reference_id,
            "category_name": category_info["category_name"],
            "vendor_name": vendor_name,
            "actual_cost": actual_cost,
            "estimated_amount": category_info["estimated_amount"],
            "total_spent": budget_plan.total_spent,
            "balance": budget_plan.balance,
            "payment_status": payment_status,
            "selected_vendor_id": user_vendor_id,
            "vendor_collection_name": vendor_collection_name,
            "selected_vendors_count": len(budget_plan.selected_vendors)
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"[ADD_VENDOR] Error adding vendor: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error adding vendor to budget category."
        )

def get_category_current_cost(reference_id: str, category_name: str) -> Dict[str, Any]:
    """Get current actual cost and other info for a category."""
    try:
        plan_dict = db[BUDGET_PLANS_COLLECTION].find_one({"reference_id": reference_id})
        if not plan_dict:
            return {}
        
        budget_plan = BudgetPlanDBSchema.model_validate(plan_dict)
        
        for category in budget_plan.budget_breakdown:
            if category.category_name.lower() == category_name.lower():
                return {
                    "category_name": category.category_name,
                    "estimated_amount": category.estimated_amount,
                    "actual_cost": category.actual_cost,
                    "percentage": category.percentage,
                    "payment_status": getattr(category, 'payment_status', None),
                    "has_actual_cost": category.actual_cost is not None
                }
        
        return {}
        
    except Exception as e:
        logger.error(f"Error getting category info for {category_name}: {e}")
        return {}