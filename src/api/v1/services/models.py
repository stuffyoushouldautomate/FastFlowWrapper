from typing import List
from pydantic import BaseModel
import time


class OpenAIModel(BaseModel):
    id: str
    object: str = "model"
    created: int = int(time.time())
    owned_by: str
    name: str
    type_: str = "chat"


class ResponseModel(BaseModel):
    object: str = "list"
    data: List[OpenAIModel]


async def get_openai_models() -> ResponseModel:
    # Make sure model name is consistent
    openai_models: List[OpenAIModel] = [
        OpenAIModel(
            id="henjii/gpt-4o",  # Verify this matches what we use in chat.py
            object="model",
            created=int(time.time()),
            owned_by="henjii",
            name="gpt-4o",
            type_="chat"
        )
    ]

    return ResponseModel(object="list", data=openai_models)
