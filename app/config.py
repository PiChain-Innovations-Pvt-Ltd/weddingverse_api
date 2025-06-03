from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional # Add this import
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
    env:                     str = Field(..., env="ENV")  # local|dev|prod
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
    # Schema directory (if used elsewhere)
    schema_dir:              str = Field(..., env="SCHEMA_DIR")

    # Gemini / GenAI
    gemini_api_key:          str = Field(..., env="GEMINI_API_KEY")

    # JWT Auth
    jwt_secret_key:          str = Field(..., env="JWT_SECRET_KEY")

    # --- Flowchart Service Configurations for REAL APIs ---
    # Salesforce URLs and Credentials
    SALESFORCE_AUTH_URL: str = Field(..., env="SALESFORCE_AUTH_URL")
    SALESFORCE_API_BASE_URL: str = Field(..., env="SALESFORCE_API_BASE_URL")
    SALESFORCE_CLIENT_ID: str = Field(..., env="SALESFORCE_CLIENT_ID")
    SALESFORCE_CLIENT_SECRET: str = Field(..., env="SALESFORCE_CLIENT_SECRET")
    SALESFORCE_USERNAME: str = Field(..., env="SALESFORCE_USERNAME")
    SALESFORCE_PASSWORD: str = Field(..., env="SALESFORCE_PASSWORD")
    SALESFORCE_SECURITY_TOKEN: Optional[str] = Field(None, env="SALESFORCE_SECURITY_TOKEN") # Optional for orgs without it

    # WhatsApp Business Cloud URL and Token
    WHATSAPP_BUSINESS_API_URL: str = Field(..., env="WHATSAPP_BUSINESS_API_URL") # Specific API endpoint for messages
    WHATSAPP_API_TOKEN: str = Field(..., env="WHATSAPP_API_TOKEN") # Your WhatsApp Business Cloud permanent access token

    # Ultravox API Configuration ---
    ULTRAVOX_BASE_URL: str = Field(..., env="ULTRAVOX_BASE_URL")
    ULTRAVOX_API_KEY: str = Field(..., env="ULTRAVOX_API_KEY")



settings = Settings()

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