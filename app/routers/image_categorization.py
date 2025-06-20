# from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
# from typing import List,Optional
# from app.services.image_categorization_services import categorize_and_match, categorize_bulk
# from app.utils.logger import logger
# from app.models.vision_board import VisionBoardResponse

# router = APIRouter()

# @router.post(
#     "",
#     summary="Extract + match wedding metadata",
#     responses={
#         200: {"description": "OK"},
#         400: {"description": "Bad Request"},
#         401: {"description": "Unauthorized"},
#         403: {"description": "Forbidden"},
#         502: {"description": "Upstream service failed"},
#         500: {"description": "Internal Server Error"},
#     },
#     # Remove the explicit API Key dependency here
#     # dependencies=[Depends(get_api_key)],
#     response_model=VisionBoardResponse
# )
# async def categorize_endpoint(
#     images:           List[UploadFile] = File(..., description="One or more images"),
#     guest_experience: str              = Form(..., description="Guest experience"),
#     events:           List[str]        = Form(default=[], description="Events list"),
#     reference_id:     str              = Form(..., description="User reference_id"),
#     location:         Optional[str]    = Form(None, description="Wedding location")
# ):

#     if not images:
#         raise HTTPException(status_code=400, detail="Provide at least one image file")
    
#     if not reference_id:
#         raise HTTPException(status_code=400, detail="please provide the reference_id")

#     try:
#         # Read all uploaded files
#         upload_bytes_list = [await img.read()    for img in images]
#         content_types     = [img.content_type     for img in images]

#         if len(images) > 1:
#             # single combined response
#             bulk_response = await categorize_bulk(
#                 upload_bytes_list,
#                 content_types,
#                 guest_experience,
#                 events,
#                 reference_id
#             )
#             return bulk_response

#         # Delegate to your service for a single image
#         single_response = await categorize_and_match(
#             upload_bytes_list,
#             content_types,
#             guest_experience,
#             events,
#             reference_id
#         )
#         return single_response

#     except HTTPException:
#         # Re-raise 400/502 from downstream
#         raise

#     except Exception:
#         logger.error("Unexpected error in /image_upload", exc_info=True)
#         raise HTTPException(
#             status_code=500,
#             detail="Internal Server Error"
#         ) 


from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from typing import List, Optional
from app.services.image_categorization_services import categorize_and_match, categorize_bulk
from app.utils.logger import logger
from app.models.vision_board import VisionBoardResponse

router = APIRouter()

@router.post(
    "",
    summary="Extract + match wedding metadata",
    responses={
        200: {"description": "OK"},
        400: {"description": "Bad Request"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        502: {"description": "Upstream service failed"},
        500: {"description": "Internal Server Error"},
    },
    response_model=VisionBoardResponse
)
async def categorize_endpoint(
    images:           List[UploadFile] = File(..., description="One or more images"),
    guest_experience: str              = Form(..., description="Guest experience"),
    events:           List[str]        = Form(default=[], description="Events list"),
    reference_id:     str              = Form(..., description="User reference_id"),
    location:         Optional[str]    = Form(None, description="Wedding location")  # ADDED: location parameter
):

    if not images:
        raise HTTPException(status_code=400, detail="Provide at least one image file")
    
    if not reference_id:
        raise HTTPException(status_code=400, detail="please provide the reference_id")

    try:
        # Read all uploaded files
        upload_bytes_list = [await img.read()    for img in images]
        content_types     = [img.content_type     for img in images]

        if len(images) > 1:
            # single combined response
            bulk_response = await categorize_bulk(
                upload_bytes_list,
                content_types,
                guest_experience,
                events,
                reference_id,
                location  # ADDED: Pass location parameter
            )
            return bulk_response

        # Delegate to your service for a single image
        single_response = await categorize_and_match(
            upload_bytes_list,
            content_types,
            guest_experience,
            events,
            reference_id,
            location  # ADDED: Pass location parameter
        )
        return single_response

    except HTTPException:
        # Re-raise 400/502 from downstream
        raise

    except Exception:
        logger.error("Unexpected error in /image_upload", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error"
        )