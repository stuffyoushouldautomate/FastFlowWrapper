from typing import List
from src.models.openai import OpenAIModel, OpenAIModelsResponse
import time

class ResponseModel(OpenAIModelsResponse):
    pass

async def get_openai_models() -> ResponseModel:
    # Return a static model list
    openai_models: List[OpenAIModel] = [
        OpenAIModel(
            id="thriveai/gpt-4o",
            object="model",
            created=int(time.time()),
            owned_by="thriveai",
            name="ThriveAI GPT-4",
            type_="chat"
        )
    ]

    return ResponseModel(object="list", data=openai_models)
