import uvicorn
from fastapi import FastAPI, Depends, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.utils.logger import logger
from app.routers import vision_board, chat, image_categorization, auth
from app.dependencies import require_jwt_auth
from app.config import settings

# Dynamically pick the correct base URL
base_url_attr = f"base_url_{settings.env}"
root_path = getattr(settings, base_url_attr, "").rstrip("/")

app = FastAPI(
    title="WeddingVerse API",
    root_path=root_path
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://weddingverse-qa.ken42.com"],  # replace with your actual client origin(s)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info(f"Starting WeddingVerse API under ENV={settings.env} at root_path={root_path}")

# JWT Dependency for protected routes
jwt_auth_deps = [Depends(require_jwt_auth)]

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])

app.include_router(
    vision_board.router,
    prefix="/api/v1/vision-board",
    dependencies=jwt_auth_deps
)

app.include_router(
    chat.router,
    prefix="/api/v1/chat",
    dependencies=jwt_auth_deps
)

app.include_router(
    image_categorization.router,
    prefix="/api/v1/image_upload",
    dependencies=jwt_auth_deps,  # Apply JWT auth to image_categorization router
    tags=["Image Categorization"]
)

@app.exception_handler(status.HTTP_401_UNAUTHORIZED)
async def unauthorized_exception_handler(request: Request, exc):
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": str(exc.detail)},
        headers={"WWW-Authenticate": "Bearer"},
    )

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
