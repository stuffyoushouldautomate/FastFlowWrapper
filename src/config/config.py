from pydantic import BaseModel
from functools import lru_cache
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseModel):
    flowise_api_base_url: str = os.getenv("FLOWISE_API_BASE_URL", "http://localhost:1234/api/v1")
    flowise_chatflow_id: str = os.getenv("FLOWISE_CHATFLOW_ID")
    api_key: str = os.getenv("API_KEY")

    def __init__(self, **data):
        super().__init__(**data)
        # Log settings for debugging
        import logging
        logger = logging.getLogger("uvicorn.error")
        logger.info(f"Loaded settings: FLOWISE_API_BASE_URL={self.flowise_api_base_url}")
        logger.info(f"Loaded settings: FLOWISE_CHATFLOW_ID={self.flowise_chatflow_id}")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
