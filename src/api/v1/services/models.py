from typing import List
from src.models.openai import OpenAIModel, OpenAIModelsResponse
import time

class ResponseModel(OpenAIModelsResponse):
    pass

async def get_openai_models() -> ResponseModel:
    # Return a static model list
    openai_models: List[OpenAIModel] = [
        OpenAIModel(
            id="henjii/gpt-4o",
            object="model",
            created=int(time.time()),
            owned_by="henjii",
            name="gpt-4o",
            type_="chat"
        )
    ]

    return ResponseModel(object="list", data=openai_models)
