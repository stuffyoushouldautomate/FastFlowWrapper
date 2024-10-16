from typing import List
import requests
import json
from fastapi import HTTPException
from src.models.flowise import FlowiseChatflow
from src.models.openai import OpenAIModel, OpenAIModelsResponse
from src.utils.helpers import iso_to_unix
from src.config.config import Settings
import logging

logger = logging.getLogger("uvicorn.error")
settings = Settings()


class ResponseModel(OpenAIModelsResponse):
    pass


async def get_openai_models() -> ResponseModel:
    FLOWISE_CHATFLOWS_URL = f"{settings.flowise_api_base_url}/chatflows"
    try:
        response = requests.get(FLOWISE_CHATFLOWS_URL)
        response.raise_for_status()
        flowise_data = response.json()
    except requests.RequestException as e:
        logger.error(f"Error fetching data from Flowise: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error fetching data from Flowise: {e}"
        )
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing Flowise response: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error parsing Flowise response: {e}"
        )

    openai_models: List[OpenAIModel] = []
    for item in flowise_data:
        try:
            chatflow = FlowiseChatflow(**item)
            model = OpenAIModel(
                id=chatflow.id,
                object="model",
                created=iso_to_unix(chatflow.createdDate),
                owned_by="flowise_user",
                name=chatflow.name or "Unnamed Chatflow",
                type_="flowise",
            )
            openai_models.append(model)
        except Exception as e:
            logger.warning(f"Skipping invalid chatflow data: {e}")
            continue

    return ResponseModel(object="list", data=openai_models)
