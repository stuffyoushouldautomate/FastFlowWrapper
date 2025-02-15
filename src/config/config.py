from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    flowise_api_base_url: str = "http://localhost:1234/api/v1"
    flowise_chatflow_id: str
    assistant_id: Optional[str] = None
    api_key: str  # Single API key
    portkey_api_key: str
    portkey_virtual_key: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
