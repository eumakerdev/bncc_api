"""
Application configuration settings
"""

import os
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    
    # API Configuration
    API_HOST: str = Field(default="0.0.0.0", description="API host")
    API_PORT: int = Field(default=8000, description="API port")
    ENVIRONMENT: str = Field(default="development", description="Environment (development/production)")
    
    # Security
    SECRET_KEY: str = Field(default="your-secret-key-change-in-production", description="Secret key for JWT")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, description="Access token expiration time")
    ALLOWED_HOSTS: List[str] = Field(default=["*"], description="Allowed CORS origins")
    
    # Database and Storage
    BNCC_DATA_PATH: str = Field(default="./data/bncc_completa.json", description="Path to BNCC JSON data")
    CHROMADB_PATH: str = Field(default="./data/chromadb", description="ChromaDB storage path")
    CHROMADB_HOST: str = Field(default="localhost", description="ChromaDB host")
    CHROMADB_PORT: int = Field(default=8001, description="ChromaDB port")
    
    # AI/ML Configuration
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key")
    GOOGLE_API_KEY: str = Field(default="", description="Google AI API key")
    EMBEDDING_MODEL: str = Field(default="sentence-transformers/all-MiniLM-L6-v2", description="Embedding model")
    LLM_MODEL: str = Field(default="gpt-3.5-turbo", description="LLM model for chat")
    MAX_TOKENS: int = Field(default=1000, description="Maximum tokens for LLM responses")
    TEMPERATURE: float = Field(default=0.7, description="LLM temperature")
    
    # Vector Search
    SIMILARITY_THRESHOLD: float = Field(default=0.7, description="Minimum similarity score for search results")
    MAX_SEARCH_RESULTS: int = Field(default=10, description="Maximum number of search results")
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = Field(default=100, description="Rate limit: requests per minute")
    RATE_LIMIT_WINDOW: int = Field(default=60, description="Rate limit window in seconds")
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
