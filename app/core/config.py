from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "MetaMusk Backend"
    API_V1_STR: str = "/api/v1"
    
    # Database
    # Defaulting to the docker-compose settings (port 5438)
    DATABASE_URL: str = "postgresql+asyncpg://admin:admin123@localhost:5438/vectordb"
    
    # LangChain / LangSmith Tracing
    LANGCHAIN_TRACING_V2: str = "false"
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: str = "metamusk-backend"

    class Config:
        case_sensitive = True
        env_file = ".env"
        # Extract extra fields from .env even if not defined here (optional, but robust)
        extra = "ignore" 

settings = Settings()
