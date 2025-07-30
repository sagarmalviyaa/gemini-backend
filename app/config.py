from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    # Database Configuration
    database_url: str = "postgresql://gemini_user:password@localhost:5432/gemini_backend"
    
    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"
    
    # JWT Configuration
    jwt_secret_key: str = "your-super-secret-jwt-key-here"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440  # 24 hours
    
    # Google Gemini API
    gemini_api_key: str = ""
    
    # Stripe Configuration
    stripe_publishable_key: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_pro_price_id: str = ""
    
    # Application Configuration
    app_name: str = "Gemini Backend Clone"
    app_version: str = "1.0.0"
    debug: bool = True
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    
    # Celery Configuration
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    
    # Rate Limiting
    basic_daily_limit: int = 5
    
    class Config:
        env_file = ".env"

settings = Settings()