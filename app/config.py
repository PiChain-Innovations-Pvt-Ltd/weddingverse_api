import json
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Dict, Any
from app.utils.logger import logger

class Settings(BaseSettings):
    """
    All config is loaded from environment / .env.
    No defaults are hard-coded here.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore" # Allow extra fields in .env not defined here
    )

    # environment
    env:                     str = Field(..., env="ENV")
    base_url_local:          str = Field(..., env="BASE_URL_LOCAL")
    base_url_dev:            str = Field(..., env="BASE_URL_DEV")
    base_url_prod:           str = Field(..., env="BASE_URL_PROD")

    # MongoDB connection
    mongo_uri:               str = Field(..., env="MONGO_URI")
    meta_data_mongo_uri:     str = Field(..., env="META_DATA_MONGO_URI")
    database_name:           str = Field(..., env="DATABASE_NAME")
    meta_data_database_name: str = Field(..., env="META_DATA_DATABASE_NAME")
    image_input_collection:  str = Field(..., env="IMAGE_INPUT_COLLECTION")
    VISION_BOARD_COLLECTION: str = Field(..., env="VISION_BOARD_COLLECTION")
    VENDOR_ONBOARDING_COLLECTION: str = Field(..., env="VENDOR_ONBOARDING_COLLECTION")
    WEDDINGVERSE_METADATA_COLLECTION: str = Field(..., env="WEDDINGVERSE_METADATA_COLLECTION")
    CHAT_CONVERSATIONS_COLLECTION: str = Field(..., env="CHAT_CONVERSATIONS_COLLECTION")
    BUDGET_PLANS_COLLECTION: str = Field(..., env="BUDGET_PLANS_COLLECTION")
    # Schema directory (if used elsewhere)
    schema_dir:              str = Field(..., env="SCHEMA_DIR")

    # Gemini / GenAI
    gemini_api_key:          str = Field(..., env="GEMINI_API_KEY")

    # NEW: Individual GCP credential fields
    GCP_TYPE:                        str = Field(..., env="GCP_TYPE")
    GCP_PROJECT_ID:                  str = Field(..., env="GCP_PROJECT_ID")
    GCP_PRIVATE_KEY_ID:              str = Field(..., env="GCP_PRIVATE_KEY_ID")
    GCP_PRIVATE_KEY:                 str = Field(..., env="GCP_PRIVATE_KEY") # This will hold the Base64 string
    GCP_CLIENT_EMAIL:                str = Field(..., env="GCP_CLIENT_EMAIL")
    GCP_CLIENT_ID:                   str = Field(..., env="GCP_CLIENT_ID")
    GCP_AUTH_URI:                    str = Field(..., env="GCP_AUTH_URI")
    GCP_TOKEN_URI:                   str = Field(..., env="GCP_TOKEN_URI")
    GCP_AUTH_PROVIDER_X509_CERT_URL: str = Field(..., env="GCP_AUTH_PROVIDER_X509_CERT_URL")
    GCP_CLIENT_X509_CERT_URL:        str = Field(..., env="GCP_CLIENT_X509_CERT_URL")
    GCP_UNIVERSE_DOMAIN:             str = Field(..., env="GCP_UNIVERSE_DOMAIN")

    # This will store the constructed and decoded dictionary
    GOOGLE_APPLICATION_CREDENTIALS: Optional[Dict[str, Any]] = None

    PROJECT_ID:              str = Field(..., env="PROJECT_ID")
    REGION:                  str = Field(..., env="REGION")
    MODEL_NAME:              str = Field(..., env="MODEL_NAME")

    # JWT Auth
    jwt_secret_key:          str = Field(..., env="JWT_SECRET_KEY")

    # --- Flowchart Service Configurations for REAL APIs ---
    SALESFORCE_AUTH_URL: str = Field(..., env="SALESFORCE_AUTH_URL")
    SALESFORCE_API_BASE_URL: str = Field(..., env="SALESFORCE_API_BASE_URL")
    SALESFORCE_CLIENT_ID: str = Field(..., env="SALESFORCE_CLIENT_ID")
    SALESFORCE_CLIENT_SECRET: str = Field(..., env="SALESFORCE_CLIENT_SECRET")
    SALESFORCE_USERNAME: str = Field(..., env="SALESFORCE_USERNAME")
    SALESFORCE_PASSWORD: str = Field(..., env="SALESFORCE_PASSWORD")
    SALESFORCE_SECURITY_TOKEN: Optional[str] = Field(None, env="SALESFORCE_SECURITY_TOKEN")

    WHATSAPP_BUSINESS_API_URL: str = Field(..., env="WHATSAPP_BUSINESS_API_URL")
    WHATSAPP_API_TOKEN: str = Field(..., env="WHATSAPP_API_TOKEN")

    ULTRAVOX_BASE_URL: str = Field(..., env="ULTRAVOX_BASE_URL")
    ULTRAVOX_API_KEY: str = Field(..., env="ULTRAVOX_API_KEY")



settings = Settings()

# Decode the private key and construct the GOOGLE_APPLICATION_CREDENTIALS dictionary
try:
    processed_private_key = settings.GCP_PRIVATE_KEY.replace('\\n', '\n')
    settings.GOOGLE_APPLICATION_CREDENTIALS = {
        "type": settings.GCP_TYPE,
        "project_id": settings.GCP_PROJECT_ID,
        "private_key_id": settings.GCP_PRIVATE_KEY_ID,
        "private_key": processed_private_key,
        "client_email": settings.GCP_CLIENT_EMAIL,
        "client_id": settings.GCP_CLIENT_ID,
        "auth_uri": settings.GCP_AUTH_URI,
        "token_uri": settings.GCP_TOKEN_URI,
        "auth_provider_x509_cert_url": settings.GCP_AUTH_PROVIDER_X509_CERT_URL,
        "client_x509_cert_url": settings.GCP_CLIENT_X509_CERT_URL,
        "universe_domain": settings.GCP_UNIVERSE_DOMAIN,
    }
except Exception as e:
    logger.error(f"Error decoding or constructing Google Application Credentials: {e}")
    raise RuntimeError(f"Error decoding or constructing Google Application Credentials: {e}. Application cannot proceed.")


print("→ loaded settings:", settings.dict(), flush=True)

# Static field‐mapping for your vision‐board queries
FIELD_MAP = {
    "wedding_preference": "data.Wedding Preference",
    "venue_suits":        "data.Venue Suits",
    "wedding_style":      "data.Wedding Style",
    "wedding_tone":       "data.Wedding Tone",
    "guest_experience":   "data.Guest Experience",
    "people_dress_code":  "data.People Dress Code",
}