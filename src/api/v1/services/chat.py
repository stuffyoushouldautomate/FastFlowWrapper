from typing import AsyncGenerator, Dict, Any
import logging
import os
import aiohttp
from src.core.logger import logger

logger = logging.getLogger("uvicorn.error")

async def handle_chat_completion(body: Dict[str, Any]) -> AsyncGenerator[str, None]:
    """Handle chat completion by forwarding to Flowise"""
    headers = {
        "Authorization": f"Bearer {os.getenv('FLOWISE_API_KEY')}",
        "Content-Type": "application/json"
    }
    
    chatflow_id = os.getenv('FLOWISE_CHATFLOW_ID')
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{os.getenv('FLOWISE_API_URL')}/prediction/{chatflow_id}/stream",
            headers=headers,
            json=body
        ) as response:
            async for chunk in response.content:
                if chunk:
                    yield f"data: {chunk.decode()}\n\n"
