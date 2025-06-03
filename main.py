## app/main.py
import uvicorn
from fastapi import FastAPI, Depends, Request, status, HTTPException
from fastapi.responses import JSONResponse

from app.utils.logger import logger
from app.routers import (
    auth,
    vision_board,
    chat,
    image_categorization,
    initial_budget_router, # For Step 1 (Initial Budget Setup)
    batch_adjust_router ,  # For Step 2 (Batch Adjust, Fixed Total)
    vendor_discovery_router,
    vendor_selection_router # ADDED: Import the new router
)
from app.dependencies import require_jwt_auth
from app.config import settings # Assuming settings.py for ENV

root_path = ""
app = FastAPI(
    title="WeddingVerse API",
    description="API for WeddingVerse application services.",
    version="1.0.0",
    root_path=root_path
)

current_env = settings.env if hasattr(settings, 'env') else 'local'
logger.info(f"Starting WeddingVerse API under ENV={current_env} at root_path='{root_path}'")

# Define JWT auth dependency to be used by protected routers
jwt_auth_deps = [Depends(require_jwt_auth)]

# Include routers with appropriate prefixes and tags
app.include_router(
    auth.router,
    prefix="/api/v1/auth",
    tags=["Authentication"]
)
app.include_router(
    vision_board.router,
    prefix="/api/v1/vision-board",
    tags=["Vision Board"],
    dependencies=jwt_auth_deps
)
app.include_router(
    chat.router,
    prefix="/api/v1/chat",
    tags=["Chat"],
    dependencies=jwt_auth_deps
)
app.include_router(
    image_categorization.router,
    prefix="/api/v1/image-categorization", # Added prefix here
    tags=["Image Categorization"],
    dependencies=jwt_auth_deps # Assuming this endpoint also needs authentication
)

# Budget-related routers (these already define their /api/v1 prefixes internally)
app.include_router(initial_budget_router.router)
app.include_router(batch_adjust_router.router)
app.include_router(vendor_discovery_router.router)
app.include_router(vendor_selection_router.router) # ADDED: Include the new router here

# --- Exception Handlers ---
@app.exception_handler(HTTPException) # General HTTPException handler
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers if hasattr(exc, "headers") else None,
    )

# Specific handler for 401, ensuring WWW-Authenticate header
@app.exception_handler(status.HTTP_401_UNAUTHORIZED)
async def unauthorized_exception_handler(request: Request, exc: HTTPException): # exc is already HTTPException
    headers = {"WWW-Authenticate": "Bearer"}
    # If the original exception had custom headers, preserve them
    if hasattr(exc, 'headers') and exc.headers:
        headers.update(exc.headers)
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": exc.detail if hasattr(exc, 'detail') else "Unauthorized"},
        headers=headers,
    )

@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Welcome to WeddingVerse API!"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")