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
                        data = decoded_line.replace("data: ", "").strip()
                        yield f"data: {data}\n\n"
    except requests.RequestException as e:
        logger.error(f"Error communicating with Flowise: {e}")
        yield f'data: {{"error": "Error communicating with Flowise: {e}"}}\n\n'
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing Flowise response: {e.msg}")
        yield f'data: {{"error": "Error parsing Flowise response: {e.msg}"}}\n\n'


async def handle_chat_completion(body: Dict[str, Any]) -> Generator[str, None, None]:
    try:
        messages = body.get("messages", [])
        if not messages:
            raise ValueError("No messages provided in the request.")

        latest_message = messages[-1]
        if latest_message.get("role", "").lower() != "user":
            raise ValueError("The latest message must be from the user.")

        flowise_request_data = {"question": latest_message.get("content", "")}

        FLOWISE_PREDICTION_URL = (
            f"{settings.flowise_api_base_url}/prediction/{settings.flowise_chatflow_id}"
        )

        generator = fetch_flowise_stream(FLOWISE_PREDICTION_URL, flowise_request_data)
        for chunk in generator:
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
