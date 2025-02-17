from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    flowise_api_base_url: str
    flowise_chatflow_id: str
    api_key: str
    port: int = 8000

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings() 