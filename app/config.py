from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Google AI Configuration
    google_api_key: str
    gemini_model: str = "gemini-1.5-flash"
    
    # Google Maps API
    google_maps_api_key: str
    
    # Firebase Configuration
    firebase_project_id: str
    firebase_private_key_id: str
    firebase_private_key: str
    firebase_client_email: str
    firebase_client_id: str
    firebase_auth_uri: str = "https://accounts.google.com/o/oauth2/auth"
    firebase_token_uri: str = "https://oauth2.googleapis.com/token"
    
    # BigQuery Configuration
    google_cloud_project_id: str
    bigquery_dataset_id: str = "wanderly_analytics"
    
    # App Configuration
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    
    class Config:
        env_file = ".env"

settings = Settings()


