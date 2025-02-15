from pydantic import BaseModel
from functools import lru_cache
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseModel):
    flowise_api_base_url: str = "http://localhost:1234/api/v1"
    flowise_chatflow_id: str = os.getenv("FLOWISE_CHATFLOW_ID")
    api_key: str = os.getenv("API_KEY")  # Single API key for authentication


@lru_cache()
def get_settings() -> Settings:
    return Settings()
