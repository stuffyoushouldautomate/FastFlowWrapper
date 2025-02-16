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
import tiktoken

logger = logging.getLogger("uvicorn.error")
settings = get_settings()


async def fetch_flowise_stream(flowise_url: str, payload: dict) -> AsyncGenerator[str, None]:
    try:
        headers = {
            "Authorization": f"Bearer {settings.api_key}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", flowise_url, json=payload, headers=headers, timeout=30.0) as response:
                response.raise_for_status()
                logger.info("Connected to Flowise stream")

                buffer = ""
                async for chunk in response.aiter_text():
                    logger.info(f"Raw chunk received: {chunk}")  # Log raw chunks
                    buffer += chunk

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        
                        if not line:
                            continue

                        try:
                            data = json.loads(line)
                            logger.info(f"Parsed data: {data}")  # Log parsed data
                            
                            if isinstance(data, dict) and "text" in data:
                                # Handle direct text response
                                content = data["text"]
                                response = {
                                    "id": f"chatcmpl-{str(uuid.uuid4())}",
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": "henjii/gpt-4o",
                                    "choices": [{
                                        "index": 0,
                                        "delta": {
                                            "content": content
                                        },
                                        "finish_reason": None
                                    }]
                                }
                                chunk = f"data: {json.dumps(response)}\n\n"
                                logger.info(f"Sending chunk: {chunk}")
                                yield chunk
                            
                            elif isinstance(data, list) and len(data) > 0:
                                messages = data[0].get("messages", [])
                                if messages and len(messages) > 1:
                                    bot_message = messages[-1]
                                    if bot_message["role"] == "bot":
                                        content = bot_message["content"]
                                        response = {
                                            "id": f"chatcmpl-{str(uuid.uuid4())}",
                                            "object": "chat.completion.chunk",
                                            "created": int(time.time()),
                                            "model": "henjii/gpt-4o",
                                            "choices": [{
                                                "index": 0,
                                                "delta": {
                                                    "content": content
                                                },
                                                "finish_reason": None
                                            }]
                                        }
                                        chunk = f"data: {json.dumps(response)}\n\n"
                                        logger.info(f"Sending chunk: {chunk}")
                                        yield chunk

                        except json.JSONDecodeError as e:
                            logger.error(f"JSON decode error: {e} for line: {line}")
                            continue

                # Send DONE after full message
                yield "data: [DONE]\n\n"
                return

    except Exception as e:
        logger.error(f"Error in fetch_flowise_stream: {e}")
        error_response = {
            "error": {
                "message": f"Streaming error: {str(e)}",
                "type": "server_error",
                "code": 500
            }
        }
        yield f"data: {json.dumps(error_response)}\n\n"
        yield "data: [DONE]\n\n"


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
