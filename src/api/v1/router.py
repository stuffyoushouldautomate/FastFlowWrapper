from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from src.api.v1.services.models import get_openai_models
from src.api.v1.services.chat import (
    handle_chat_completion,
    handle_chat_completion_sync,
)
from src.models.openai import ChatCompletionRequest, ChatCompletionResponse

router = APIRouter()


@router.get("/v1/models", response_model=None, tags=["Models"])
async def get_models():
    return await get_openai_models()


@router.post("/v1/chat/completions", tags=["Completions"])
async def create_chat_completion(chat_request: ChatCompletionRequest):
    if chat_request.stream:
        return StreamingResponse(
            handle_chat_completion(chat_request.dict()), media_type="text/event-stream"
        )
    else:
        response = await handle_chat_completion_sync(chat_request.dict())
        return JSONResponse(content=response)
