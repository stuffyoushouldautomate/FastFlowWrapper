from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from src.api.v1.services.models import get_openai_models
from src.api.v1.services.chat import (
    handle_chat_completion,
    handle_chat_completion_sync,
)
from src.models.openai import ChatCompletionRequest

router = APIRouter()


@router.get("/v1/models", response_model=None, tags=["Models"])
async def get_models():
    return await get_openai_models()


@router.post("/v1/chat/completions", tags=["Completions"])
async def create_chat_completion(request: Request):
    # Get raw request body
    body = await request.json()
    
    # Check if it's a streaming request
    stream = body.get("stream", False)
    
    if stream:
        return StreamingResponse(
            handle_chat_completion(body),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
                "Transfer-Encoding": "chunked"
            }
        )
    else:
        response = await handle_chat_completion_sync(body)
        return JSONResponse(content=response)
