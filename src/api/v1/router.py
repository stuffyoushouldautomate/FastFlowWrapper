from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from src.api.v1.services.models import get_openai_models
from src.api.v1.services.chat import (
    handle_chat_completion,
    handle_chat_completion_sync,
)
from src.models.openai import ChatCompletionRequest, ChatCompletionResponse
from typing import Dict, Any
import logging

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/v1/models", response_model=None, tags=["Models"])
async def get_models():
    return await get_openai_models()


@router.post("/chat/completions")
async def chat_completion(
    body: Dict[str, Any],
    stream: bool = Query(default=False)
) -> Dict[str, Any]:
    try:
        if stream:
            return StreamingResponse(
                handle_chat_completion(body),
                media_type="text/event-stream"
            )
        return await handle_chat_completion_sync(body)
    except Exception as e:
        logger.error(f"Chat completion error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
