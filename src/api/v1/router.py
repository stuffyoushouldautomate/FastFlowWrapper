from fastapi import APIRouter, HTTPException
from typing import List
import requests
import json

from src.models.flowise import FlowiseChatflow
from src.models.openai import (
    OpenAIModel,
    OpenAIModelsResponse,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ChatChoice,
    ChatUsage,
)
from src.utils.helpers import iso_to_unix
from src.config.config import Settings

router = APIRouter()

settings = Settings()


@router.get("/v1/models", response_model=OpenAIModelsResponse, tags=["Models"])
def get_models():
    FLOWISE_CHATFLOWS_URL = f"{settings.flowise_api_base_url}/chatflows"

    try:
        response = requests.get(FLOWISE_CHATFLOWS_URL)
        response.raise_for_status()
        flowise_data = response.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching data from Flowise: {e}"
        )
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500, detail=f"Error parsing Flowise response: {e.msg}"
        )

    openai_models: List[OpenAIModel] = []

    for item in flowise_data:
        chatflow = FlowiseChatflow(**item)

        model = OpenAIModel(
            id=chatflow.id,
            created=iso_to_unix(chatflow.createdDate),
            owned_by="flowise_user",
            name=chatflow.name,
            model_type="flowise", 
        )
        openai_models.append(model)

    return OpenAIModelsResponse(data=openai_models)


@router.post(
    "/v1/chat/completions", response_model=ChatCompletionResponse, tags=["Completions"]
)
def create_chat_completion(request: ChatCompletionRequest):
    FLOWISE_PREDICTION_URL = (
        f"{settings.flowise_api_base_url}/prediction/{settings.flowise_chatflow_id}"
    )

    flowise_request_data = {"question": request.messages[-1].content}

    try:
        response = requests.post(
            FLOWISE_PREDICTION_URL, json=flowise_request_data, timeout=30
        )
        response.raise_for_status()
        flowise_response = response.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=500, detail=f"Error communicating with Flowise: {str(e)}"
        )
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500, detail=f"Error parsing Flowise response: {e.msg}"
        )

    chat_message = ChatMessage(
        role="assistant", content=flowise_response.get("text", "")
    )

    chat_choice = ChatChoice(index=0, message=chat_message, finish_reason="stop")

    chat_usage = ChatUsage(
        prompt_tokens=None, completion_tokens=None, total_tokens=None
    )

    chat_completion_response = ChatCompletionResponse(
        id=flowise_response.get("chatMessageId", "chatcmpl-unknown"),
        object="chat.completion",
        created=iso_to_unix(flowise_response.get("createdDate")),
        model=request.model,
        choices=[chat_choice],
        usage=chat_usage,
    )

    return chat_completion_response
