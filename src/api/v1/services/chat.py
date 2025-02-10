from typing import Generator, Dict, Any
import requests
import json
from src.config.config import Settings
import logging
from fastapi import HTTPException
import time
import uuid

logger = logging.getLogger("uvicorn.error")
settings = Settings()


def fetch_flowise_stream(flowise_url: str, payload: dict) -> Generator[str, None, None]:
    try:
        with requests.post(
            flowise_url, json=payload, stream=True, timeout=30
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode("utf-8")
                    if decoded_line.strip() == "[DONE]":
                        break
                    if decoded_line.startswith("data:"):
                        data = json.loads(decoded_line.replace("data: ", "").strip())
                        # Transform to OpenAI streaming format
                        chunk = {
                            "id": f"chatcmpl-{str(uuid.uuid4())}",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": "thrive/gpt-4o",
                            "choices": [{
                                "index": 0,
                                "delta": {
                                    "role": "assistant",
                                    "content": data.get("text", "")
                                },
                                "finish_reason": None
                            }]
                        }
                        yield f"data: {json.dumps(chunk)}\n\n"
            # Send final [DONE] message
            yield "data: [DONE]\n\n"
    except requests.RequestException as e:
        logger.error(f"Error communicating with Flowise: {e}")
        yield f'data: {{"error": "Error communicating with Flowise: {e}"}}\n\n'
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing Flowise response: {e.msg}")
        yield f'data: {{"error": "Error parsing Flowise response: {e.msg}"}}\n\n'


async def handle_chat_completion(body: Dict[str, Any]) -> Generator[str, None, None]:
    try:
        # Handle both standard OpenAI format and Thrive format
        content = body.get("content") if "content" in body else None
        if content is None:
            # Try OpenAI format
            messages = body.get("messages", [])
            if not messages:
                raise ValueError("No messages provided in the request.")
            content = messages[-1].get("content", "")

        flowise_request_data = {"question": content}

        FLOWISE_PREDICTION_URL = (
            f"{settings.flowise_api_base_url}/prediction/{settings.flowise_chatflow_id}"
        )

        # Check if the request is from Thrive (has object="message")
        if body.get("object") == "message":
            # Stream in Thrive format
            for chunk in fetch_flowise_stream(FLOWISE_PREDICTION_URL, flowise_request_data):
                if chunk.startswith('data: '):
                    try:
                        data = json.loads(chunk.replace('data: ', ''))
                        if isinstance(data, dict) and "choices" in data:
                            # Extract content from OpenAI format
                            content = data["choices"][0]["delta"].get("content", "")
                        else:
                            content = data.get("text", "")
                            
                        response = {
                            "object": "message",
                            "id": str(uuid.uuid4()),
                            "model": body.get("model", "thrive/gpt-4o"),
                            "role": "assistant",
                            "content": content,
                            "created_at": int(time.time())
                        }
                        yield f"data: {json.dumps(response)}\n\n"
                    except json.JSONDecodeError:
                        continue
        else:
            # Stream in OpenAI format
            for chunk in fetch_flowise_stream(FLOWISE_PREDICTION_URL, flowise_request_data):
                yield chunk

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        yield f'data: {{"error": "{e}"}}\n\n'
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        yield f'data: {{"error": "Unexpected error: {e}"}}\n\n'


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
        # Handle both standard OpenAI format and Thrive format
        content = body.get("content") if "content" in body else None
        if content is None:
            # Try OpenAI format
            messages = body.get("messages", [])
            if not messages:
                raise ValueError("No messages provided in the request.")
            content = messages[-1].get("content", "")
        
        flowise_request_data = {"question": content}

        FLOWISE_PREDICTION_URL = (
            f"{settings.flowise_api_base_url}/prediction/{settings.flowise_chatflow_id}"
        )

        flowise_response = fetch_flowise_response(
            FLOWISE_PREDICTION_URL, flowise_request_data
        )

        # Check if the request is from Thrive (has object="message")
        if body.get("object") == "message":
            # Return Thrive format
            return {
                "object": "message",
                "id": str(uuid.uuid4()),
                "model": body.get("model", "thrive/gpt-4o"),
                "role": "assistant",
                "content": flowise_response.get("text", ""),
                "created_at": int(time.time())
            }
        else:
            # Return OpenAI format
            return {
                "id": f"chatcmpl-{str(uuid.uuid4())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": body.get("model", "thrive/gpt-4o"),
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
