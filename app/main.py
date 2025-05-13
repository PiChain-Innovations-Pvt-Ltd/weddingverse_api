import uvicorn
from fastapi import FastAPI, Depends
from app.utils.logger import logger
from app.routers import vision_board, chat, image_categorization
from app.config import settings
from app.dependencies import get_api_key

# Dynamically pick the correct base URL
base_url_attr = f"base_url_{settings.env}"
root_path = getattr(settings, base_url_attr, "").rstrip("/")

app = FastAPI(
    title="WeddingVerse API",
    root_path=root_path
)

logger.info(f"Starting WeddingVerse API under ENV={settings.env} at root_path={root_path}")

# All routes require the API key
common_deps = [Depends(get_api_key)]

app.include_router(
    vision_board.router,
    prefix="/api/v1/vision-board",
    dependencies=common_deps
)
app.include_router(
    chat.router,
    prefix="/api/v1/chat",
    dependencies=common_deps
)
app.include_router(
    image_categorization.router,
    prefix="/api/v1/image_upload",
    dependencies=common_deps
)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=5000, reload=True)
