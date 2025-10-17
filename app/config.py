from pydantic_settings import BaseSettings
from typing import Optional, Dict, List

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
    
    # Currency Configuration
    default_currency: str = "INR"
    enable_currency_auto_detection: bool = True
    currency_detection_api_key: Optional[str] = None
    
    # External URL Templates - Made more generic
    google_search_url_template: str = "https://www.google.com/search?q={query}"
    google_maps_place_url_template: str = "https://www.google.com/maps/place/?q=place_id:{place_id}"
    google_maps_photo_url_template: str = "https://maps.googleapis.com/maps/api/place/photo?maxwidth={maxwidth}&photoreference={photoreference}&key={api_key}"
    
    # Alternative search engines (configurable)
    bing_search_url_template: str = "https://www.bing.com/search?q={query}"
    duckduckgo_search_url_template: str = "https://duckduckgo.com/?q={query}"
    
    # Suggestion Configuration - Made more flexible
    default_suggestion_count: int = 8 
    max_suggestion_count: int = 15  
    min_suggestion_count: int = 3  
    stay_suggestion_count: int = 4  
    travel_suggestion_count: int = 3  
    eat_suggestion_count: int = 3  
    itinerary_suggestion_count: int = 2
    
    # Default Rating and Review Values - Made more conservative
    default_rating: float = 4.0  # Reduced from 4.2
    default_reviews_count: int = 100  # Reduced from 150
    min_rating: float = 3.0  # Reduced from 3.5
    max_rating: float = 4.5  # Reduced from 4.8
    
    # API Endpoints Configuration - Made more generic
    api_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    production_api_url: Optional[str] = None
    production_frontend_url: Optional[str] = None
    
    # Environment Configuration
    environment: str = "development"  # development, staging, production
    
    # Additional Configuration Options
    enable_ai_suggestions: bool = True
    enable_maps_integration: bool = True
    enable_currency_conversion: bool = False  # Disabled by default
    fallback_to_basic_suggestions: bool = True
    
    # Regional Configuration
    default_language: str = "en"
    default_timezone: str = "UTC"
    default_country: str = "US"  # Changed from India-centric to global default
    
    @property
    def is_production(self) -> bool:
        return self.environment == "production"
    
    @property
    def effective_api_url(self) -> str:
        """Get the effective API URL based on environment"""
        if self.is_production and self.production_api_url:
            return self.production_api_url
        return self.api_base_url
    
    @property
    def effective_frontend_url(self) -> str:
        """Get the effective frontend URL based on environment"""
        if self.is_production and self.production_frontend_url:
            return self.production_frontend_url
        return self.frontend_url
    
    def get_search_url_template(self, search_engine: str = "google") -> str:
        """Get search URL template based on search engine preference"""
        templates = {
            "google": self.google_search_url_template,
            "bing": self.bing_search_url_template,
            "duckduckgo": self.duckduckgo_search_url_template
        }
        return templates.get(search_engine.lower(), self.google_search_url_template)
    
    def get_suggestion_count_for_room_type(self, room_type: str) -> int:
        """Get suggestion count based on room type"""
        counts = {
            "stay": self.stay_suggestion_count,
            "travel": self.travel_suggestion_count,
            "eat": self.eat_suggestion_count,
            "itinerary": self.itinerary_suggestion_count
        }
        return counts.get(room_type.lower(), self.default_suggestion_count)
    
    def get_rating_range(self) -> tuple:
        """Get min and max rating range"""
        return (self.min_rating, self.max_rating)
    
    def is_feature_enabled(self, feature: str) -> bool:
        """Check if a feature is enabled"""
        feature_map = {
            "ai_suggestions": self.enable_ai_suggestions,
            "maps_integration": self.enable_maps_integration,
            "currency_conversion": self.enable_currency_conversion,
            "currency_auto_detection": self.enable_currency_auto_detection,
            "fallback_suggestions": self.fallback_to_basic_suggestions
        }
        return feature_map.get(feature, False)
    
    class Config:
        env_file = ".env"

settings = Settings()


