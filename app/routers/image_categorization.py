from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, status
from typing import List
from app.services.image_categorization_services import categorize_and_match, categorize_bulk
from app.dependencies import get_api_key
from app.utils.logger import logger

router = APIRouter()

@router.post(
    "",
    summary="Extract + match wedding metadata",
    responses={
        200: {"description": "OK"},
        400: {"description": "Bad Request"},
        401: {"description": "Missing API Key"},
        403: {"description": "Invalid API Key"},
        502: {"description": "Upstream service failed"},
        500: {"description": "Internal Server Error"},
    },
    dependencies=[Depends(get_api_key)]
)
async def categorize_endpoint(
    images:           List[UploadFile] = File(..., description="One or more images"),
    guest_experience: str              = Form(..., description="Guest experience"),
    events:           List[str]        = Form(default=[], description="Events list"),
):
    """
    Upload images, extract metadata via Gemini, match in MongoDB (including
    colors & events), generate a title & summary, and return the results.
    """
    if not images:
        raise HTTPException(status_code=400, detail="Provide at least one image file")

    try:
        # Read all uploaded files
        upload_bytes_list = [await img.read()    for img in images]
        content_types     = [img.content_type     for img in images]

        if len(images) > 1:
            # single combined response
            bulk = await categorize_bulk(
                upload_bytes_list,
                content_types,
                guest_experience,
                events
            )
            return bulk

        # Delegate to your service
        results = categorize_and_match(
            upload_bytes_list,
            content_types,
            guest_experience,
            events
        )
        return results

    except HTTPException:
        # Re-raise 400/502 from downstream
        raise

    except Exception:
        logger.error("Unexpected error in /categorize", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error"
        )
