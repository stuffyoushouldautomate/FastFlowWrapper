from pydantic_settings import BaseSettings
import os
import logging

logger = logging.getLogger("uvicorn.error")

class Settings(BaseSettings):
    flowise_api_base_url: str = "http://localhost:1234/api/v1"
    flowise_chatflow_id: str
    openai_api_key: str = os.getenv("OPENAI_API_KEY")
    assistant_id: str = os.getenv("ASSISTANT_ID")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Log settings (but mask sensitive values)
        logger.info(f"OpenAI API Key configured: {'Yes' if self.openai_api_key else 'No'}")
        logger.info(f"Assistant ID configured: {self.assistant_id}")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
