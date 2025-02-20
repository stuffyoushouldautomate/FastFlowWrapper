from typing import AsyncGenerator, Dict, Any, List
import json
from src.config.config import get_settings
import logging
import time
import uuid
import asyncio
from fastapi import HTTPException
import httpx
import tiktoken
from src.core.config import settings
from src.core.logger import logger
import os
import aiohttp

logger = logging.getLogger("uvicorn.error")
settings = get_settings()

# In-memory store for conversation history
conversation_history = {}

FLOWISE_API_URL = os.getenv("FLOWISE_API_URL", "http://localhost:3000/api/v1")
FLOWISE_API_KEY = os.getenv("FLOWISE_API_KEY", "")

def format_message_content(content: Any) -> str:
    """Format message content into plain text"""
    if isinstance(content, list):
        # Extract text from message parts
        return " ".join(
            part["text"] for part in content 
            if part.get("type") == "text" and "text" in part
        )
    return str(content)

def summarize_history(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Format messages for Flowise history"""
    return [
        {
            "role": "user" if msg.get("role") == "user" else "bot",
            "content": format_message_content(msg.get("content", "")),
            "time": msg.get("created_at", int(time.time()))
        }
        for msg in messages
    ]

async def fetch_flowise_stream(flowise_url: str, payload: dict, headers: dict) -> AsyncGenerator[str, None]:
    """Simple passthrough to Flowise"""
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", flowise_url, json=payload, headers=headers, timeout=30.0) as response:
            async for chunk in response.aiter_text():
                if chunk:
                    yield chunk

async def handle_chat_completion(body: Dict[str, Any]) -> AsyncGenerator[str, None]:
    """Handle chat completion by forwarding to Flowise"""
    headers = {
        "Authorization": f"Bearer {FLOWISE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{FLOWISE_API_URL}/prediction/stream",
            headers=headers,
            json=body
        ) as response:
            async for chunk in response.content:
                if chunk:
                    yield f"data: {chunk.decode()}\n\n"

def fetch_flowise_response(flowise_url: str, payload: dict) -> Dict[str, Any]:
    try:
        logger.info(f"Sending request to Flowise URL: {flowise_url}")
        logger.info(f"Request payload: {json.dumps(payload)}")
        
        # Add Authorization header for Flowise
        headers = {
            "Authorization": f"Bearer {settings.api_key}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(flowise_url, json=payload, headers=headers, timeout=30)
        logger.info(f"Flowise response status: {response.status_code}")
        
        response.raise_for_status()
        response_json = response.json()
        logger.info(f"Flowise response: {json.dumps(response_json)}")
        
        return response_json
    except requests.RequestException as e:
        logger.error(f"Error communicating with Flowise: {e}")
        logger.error(f"Response content: {getattr(e.response, 'text', 'No response content')}")
        raise HTTPException(
            status_code=500, detail=f"Error communicating with Flowise: {e}"
        )


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count the number of tokens in a text string."""
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception as e:
        logger.error(f"Error counting tokens: {e}")
        return 0


async def handle_chat_completion_sync(body: Dict[str, Any]) -> Dict[str, Any]:
    try:
        logger.info(f"Received request body: {json.dumps(body)}")
        
        # Get content from messages
        messages = body.get("messages", [])
        if not messages:
            raise ValueError("No messages provided in the request.")
        content = messages[-1].get("content", "")
        
        # Get model and strip provider prefix
        model = body.get("model", "gpt-4o").split("/")[-1]
        
        # Extract or generate session ID
        session_id = (
            body.get("session_id")
            or f"thread_{str(uuid.uuid4()).replace('-', '')}"
        )
        
        flowise_request_data = {
            "question": content,
            "overrideConfig": {
                "model": model,
                "systemMessage": "You are an AI assistant powered by Henjii Digital Era."
            },
            "sessionId": session_id,
            "history": messages[:-1]
        }

        logger.info(f"Prepared Flowise request data: {json.dumps(flowise_request_data)}")

        FLOWISE_PREDICTION_URL = (
            f"{settings.flowise_api_base_url}/prediction/{settings.flowise_chatflow_id}"
        )
        
        flowise_response = fetch_flowise_response(
            FLOWISE_PREDICTION_URL, flowise_request_data
        )

        # Calculate token usage
        response_text = flowise_response.get("text", "")
        prompt_tokens = sum(count_tokens(msg["content"]) for msg in messages)
        completion_tokens = count_tokens(response_text)
        total_tokens = prompt_tokens + completion_tokens

        response = {
            "id": f"chatcmpl-{str(uuid.uuid4())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": body.get("model", "henjii/gpt-4o"),
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens
            },
            "session_id": session_id
        }
        
        logger.info(f"Token usage - Prompt: {prompt_tokens}, Completion: {completion_tokens}, Total: {total_tokens}")
        logger.info(f"Returning response: {json.dumps(response)}")
        return response

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in handle_chat_completion_sync: {str(e)}")
        logger.exception("Full traceback:")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
