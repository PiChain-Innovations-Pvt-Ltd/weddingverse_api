
# app/config.py

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    All config is loaded from environment / .env.
    No defaults are hard-coded here.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False
    )

    # environment
    env:                     str = Field(..., env="ENV")  # local|dev|prod
    base_url_local:          str = Field(..., env="BASE_URL_LOCAL")
    base_url_dev:            str = Field(..., env="BASE_URL_DEV")
    base_url_prod:           str = Field(..., env="BASE_URL_PROD")

    # MongoDB connection
    mongo_uri:               str = Field(..., env="MONGO_URI")
    database_name:           str = Field(..., env="DATABASE_NAME")
    image_input_collection:  str = Field(..., env="IMAGE_INPUT_COLLECTION")
    output_collection:       str = Field(..., env="OUTPUT_COLLECTION")

    # Schema directory (if used elsewhere)
    schema_dir:              str = Field(..., env="SCHEMA_DIR")

    # Gemini / GenAI
    gemini_api_key:          str = Field(..., env="GEMINI_API_KEY")

    # JWT Auth
    jwt_secret_key:          str = Field(..., env="JWT_SECRET_KEY")

settings = Settings()

# Static field‐mapping for your vision‐board queries
FIELD_MAP = {
    "wedding_preference": "data.Wedding Preference",
    "venue_suits":        "data.Venue Suits",
    "wedding_style":      "data.Wedding Style",
    "wedding_tone":       "data.Wedding Tone",
    "guest_experience":   "data.Guest Experience",
    "people_dress_code":  "data.People Dress Code",
}