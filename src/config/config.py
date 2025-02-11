from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    flowise_api_base_url: str = "http://localhost:1234/api/v1"
    flowise_chatflow_id: str
    openai_api_key: str = os.getenv("OPENAI_API_KEY")
    assistant_id: str = os.getenv("ASSISTANT_ID")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
