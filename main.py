# # import uvicorn
# # from fastapi import FastAPI, Depends, Request, status
# # from fastapi.responses import JSONResponse
# # from fastapi.middleware.cors import CORSMiddleware
# # from app.utils.logger import logger
# # from app.routers import vision_board, chat, image_categorization, auth, webhook, initial_budget_router, batch_adjust_router, vendor_discovery_router, vendor_selection_router,budget_retrieval_router
# # from app.services import webhook_workflow_service
# # from app.dependencies import require_jwt_auth
# # from app.config import settings

# # # Dynamically pick the correct base URL
# # base_url_attr = f"base_url_{settings.env}"
# # root_path = getattr(settings, base_url_attr, "").rstrip("/")

# # app = FastAPI(
# #     title="WeddingVerse API",
# #     root_path=root_path
# # )

# # # CORS middleware
# # app.add_middleware(
# #     CORSMiddleware,
# #     allow_origins=["http://localhost:5173", "https://weddingverse-qa.ken42.com"],  # replace with your actual client origin(s)
# #     allow_credentials=True,
# #     allow_methods=["*"],
# #     allow_headers=["*"],
# # )

# # logger.info(f"Starting WeddingVerse API under ENV={settings.env} at root_path={root_path}")

# # # JWT Dependency for protected routes
# # jwt_auth_deps = [Depends(require_jwt_auth)]

# # # Include routers
# # app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])

# # app.include_router(
# #     vision_board.router,
# #     prefix="/api/v1/vision-board",
# #     dependencies=jwt_auth_deps
# # )

# # app.include_router(
# #     chat.router,
# #     prefix="/api/v1/chat",
# #     dependencies=jwt_auth_deps
# # )

# # app.include_router(
# #     image_categorization.router,
# #     prefix="/api/v1/image_upload",
# #     dependencies=jwt_auth_deps,  # Apply JWT auth to image_categorization router
# #     tags=["Image Categorization"]
# # )

# # # --- NEW: Include the webhook router ---
# # app.include_router(
# #     webhook.router, # Use the new webhook router
# #     prefix="/api/v1", # The webhook path is /api/v1/webhook
# #     tags=["Webhook Workflow"]
# # )

# # # Budget-related routers (these already define their /api/v1 prefixes internally)
# # app.include_router(initial_budget_router.router)
# # app.include_router(batch_adjust_router.router)
# # app.include_router(budget_retrieval_router.router) 
# # app.include_router(vendor_discovery_router.router)
# # app.include_router(vendor_selection_router.router) # ADDED: Include the new router here


# # @app.exception_handler(status.HTTP_401_UNAUTHORIZED)
# # async def unauthorized_exception_handler(request: Request, exc):
# #     return JSONResponse(
# #         status_code=status.HTTP_401_UNAUTHORIZED,
# #         content={"detail": str(exc.detail)},
# #         headers={"WWW-Authenticate": "Bearer"},
# #     )

# # @app.on_event("shutdown")
# # async def shutdown_event():
# #     await webhook_workflow_service.shutdown_httpx_client()
# #     logger.info("Application shutdown complete.")

# # if __name__ == "__main__":
# #     uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


# import uvicorn
# from fastapi import FastAPI, Depends, Request, status
# from fastapi.responses import JSONResponse
# from fastapi.middleware.cors import CORSMiddleware
# from app.utils.logger import logger
# from app.routers import (
#     vision_board, 
#     chat, 
#     image_categorization, 
#     auth, 
#     webhook, 
#     initial_budget_router, 
#     batch_adjust_router, 
#     vendor_discovery_router, 
#     vendor_details_router,  # Only the main vendor details router
#     vendor_selection_router,
#     budget_retrieval_router
# )
# from app.services import webhook_workflow_service
# from app.dependencies import require_jwt_auth
# from app.config import settings

# # Dynamically pick the correct base URL
# base_url_attr = f"base_url_{settings.env}"
# root_path = getattr(settings, base_url_attr, "").rstrip("/")

# app = FastAPI(
#     title="WeddingVerse API",
#     root_path=root_path
# )

# # CORS middleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:5173", "https://weddingverse-qa.ken42.com"],  # replace with your actual client origin(s)
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# logger.info(f"Starting WeddingVerse API under ENV={settings.env} at root_path={root_path}")

# # JWT Dependency for protected routes
# jwt_auth_deps = [Depends(require_jwt_auth)]

# # Include routers
# app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])

# app.include_router(
#     vision_board.router,
#     prefix="/api/v1/vision-board",
#     dependencies=jwt_auth_deps
# )

# app.include_router(
#     chat.router,
#     prefix="/api/v1/chat",
#     dependencies=jwt_auth_deps
# )

# app.include_router(
#     image_categorization.router,
#     prefix="/api/v1/image_upload",
#     dependencies=jwt_auth_deps,  # Apply JWT auth to image_categorization router
#     tags=["Image Categorization"]
# )

# # --- Include the webhook router ---
# app.include_router(
#     webhook.router, # Use the new webhook router
#     prefix="/api/v1", # The webhook path is /api/v1/webhook
#     tags=["Webhook Workflow"]
# )

# # Budget-related routers (these already define their /api/v1 prefixes internally)
# app.include_router(initial_budget_router.router)
# app.include_router(batch_adjust_router.router)
# app.include_router(budget_retrieval_router.router) 

# # Vendor-related routers
# app.include_router(vendor_discovery_router.router)  # Vendor discovery/exploration
# app.include_router(vendor_discovery_router.utility_router)  # Keep utility router for supported-categories
# app.include_router(vendor_details_router.router)  # Only the main vendor details endpoint
# app.include_router(vendor_selection_router.router)  # Vendor selection for budget


# @app.exception_handler(status.HTTP_401_UNAUTHORIZED)
# async def unauthorized_exception_handler(request: Request, exc):
#     return JSONResponse(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         content={"detail": str(exc.detail)},
#         headers={"WWW-Authenticate": "Bearer"},
#     )

# @app.on_event("shutdown")
# async def shutdown_event():
#     await webhook_workflow_service.shutdown_httpx_client()
#     logger.info("Application shutdown complete.")

# if __name__ == "__main__":
#     uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True) 


import uvicorn
from fastapi import FastAPI, Depends, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.utils.logger import logger
from app.routers import (
    vision_board, 
    chat, 
    image_categorization, 
    auth, 
    webhook, 
    initial_budget_router, 
    batch_adjust_router, 
    vendor_discovery_router, 
    vendor_details_router,  # Only the main vendor details router
    vendor_selection_router,
    budget_retrieval_router
)
from app.services import webhook_workflow_service
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

# --- Include the webhook router ---
app.include_router(
    webhook.router, # Use the new webhook router
    prefix="/api/v1", # The webhook path is /api/v1/webhook
    tags=["Webhook Workflow"]
)

# Budget-related routers (these already define their /api/v1 prefixes internally)
app.include_router(initial_budget_router.router)
app.include_router(batch_adjust_router.router)
app.include_router(budget_retrieval_router.router) 

# Vendor-related routers
app.include_router(vendor_discovery_router.router)  # Vendor discovery/exploration
app.include_router(vendor_details_router.router)  # Vendor details for messaging
app.include_router(vendor_selection_router.router)  # Vendor selection for budget


@app.exception_handler(status.HTTP_401_UNAUTHORIZED)
async def unauthorized_exception_handler(request: Request, exc):
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": str(exc.detail)},
        headers={"WWW-Authenticate": "Bearer"},
    )

@app.on_event("shutdown")
async def shutdown_event():
    await webhook_workflow_service.shutdown_httpx_client()
    logger.info("Application shutdown complete.")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)