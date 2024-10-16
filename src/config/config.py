from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    flowise_api_base_url: str = "http://localhost:1234/api/v1"
    flowise_chatflow_id: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
