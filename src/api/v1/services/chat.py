from typing import AsyncGenerator, Dict, Any
import httpx
import json
from src.config.config import get_settings
import logging
import time
import uuid
import asyncio
from fastapi import HTTPException
import requests

logger = logging.getLogger("uvicorn.error")
settings = get_settings()


async def fetch_flowise_stream(flowise_url: str, payload: dict) -> AsyncGenerator[str, None]:
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", flowise_url, json=payload, timeout=30.0) as response:
                response.raise_for_status()
                logger.info("Connected to Flowise stream")

                buffer = ""
                async for chunk in response.aiter_text():
                    logger.info(f"Raw chunk: {chunk}")
                    buffer += chunk

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        
                        if not line:
                            continue

                        try:
                            data = json.loads(line)
                            logger.info(f"Parsed data: {data}")
                            
                            if isinstance(data, list) and len(data) > 0:
                                messages = data[0].get("messages", [])
                                if messages and len(messages) > 1:
                                    bot_message = messages[-1]
                                    if bot_message["role"] == "bot":
                                        content = bot_message["content"]
                                        
                                        # Stream each word
                                        words = content.split()
                                        for word in words:
                                            response = {
                                                "id": f"chatcmpl-{str(uuid.uuid4())}",
                                                "object": "chat.completion.chunk",
                                                "created": int(time.time()),
                                                "model": "henjii/gpt-4o",
                                                "choices": [{
                                                    "index": 0,
                                                    "delta": {
                                                        "content": word + " "
                                                    },
                                                    "finish_reason": None
                                                }]
                                            }
                                            
                                            chunk = f"data: {json.dumps(response)}\n\n"
                                            logger.info(f"Sending chunk: {chunk}")
                                            yield chunk
                                            await asyncio.sleep(0.05)  # Reduced delay
                                        
                                        # Send DONE after full message
                                        yield "data: [DONE]\n\n"
                                        return

                        except json.JSONDecodeError as e:
                            logger.error(f"JSON decode error: {e} for line: {line}")
                            continue

    except Exception as e:
        logger.error(f"Error in fetch_flowise_stream: {e}")
        yield f'data: {{"error": "Streaming error: {str(e)}"}}\n\n'


async def handle_chat_completion(body: Dict[str, Any]) -> AsyncGenerator[str, None]:
    try:
        messages = body.get("messages", [])
        if not messages:
            raise ValueError("No messages provided in the request.")

        # Get model preferences and strip provider prefix if present
        primary_model = body.get("model", "").split("/")[-1]  # Strip provider prefix
        
        # Format request for Flowise
        flowise_request_data = {
            "question": messages[-1]["content"],
            "overrideConfig": {
                "model": primary_model,
                "systemMessage": "You are an AI assistant powered by Henjii Digital Era."
            },
            "sessionId": f"thread_{str(uuid.uuid4()).replace('-', '')}",
            "streaming": True
        }

        FLOWISE_PREDICTION_URL = (
            f"{settings.flowise_api_base_url}/prediction/{settings.flowise_chatflow_id}"
        )

        logger.info(f"Sending request to Flowise: {json.dumps(flowise_request_data)}")
        
        async for chunk in fetch_flowise_stream(FLOWISE_PREDICTION_URL, flowise_request_data):
            yield chunk

    except Exception as e:
        logger.error(f"Error in handle_chat_completion: {e}")
        yield f'data: {{"error": "Error: {str(e)}"}}\n\n'


def fetch_flowise_response(flowise_url: str, payload: dict) -> Dict[str, Any]:
    try:
        response = requests.post(flowise_url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error communicating with Flowise: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error communicating with Flowise: {e}"
        )
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing Flowise response: {e.msg}")
        raise HTTPException(
            status_code=500, detail=f"Error parsing Flowise response: {e.msg}"
        )


async def handle_chat_completion_sync(body: Dict[str, Any]) -> Dict[str, Any]:
    try:
        # Get content from either format
        content = body.get("content") if "content" in body else None
        if content is None:
            messages = body.get("messages", [])
            if not messages:
                raise ValueError("No messages provided in the request.")
            content = messages[-1].get("content", "")
        
        # Get model and strip provider prefix
        model = body.get("model", "gpt-4o").split("/")[-1]
        
        flowise_request_data = {
            "question": content,
            "overrideConfig": {
                "model": model
            }
        }

        FLOWISE_PREDICTION_URL = (
            f"{settings.flowise_api_base_url}/prediction/{settings.flowise_chatflow_id}"
        )

        flowise_response = fetch_flowise_response(
            FLOWISE_PREDICTION_URL, flowise_request_data
        )

        # Return OpenAI format
        return {
            "id": f"chatcmpl-{str(uuid.uuid4())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": body.get("model", "henjii/gpt-4o"),
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": flowise_response.get("text", "")
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
        }

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Unexpected error occurred.")
