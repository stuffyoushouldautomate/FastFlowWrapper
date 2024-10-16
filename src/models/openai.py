from pydantic import BaseModel, Field
from typing import List, Optional


class OpenAIModel(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str
    name: Optional[str] = None
    type_: Optional[str] = None


class OpenAIModelsResponse(BaseModel):
    object: str = "list"
    data: List[OpenAIModel]


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    stream: bool = Field(default=False)
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = None
    session_id: Optional[str] = None
    chat_id: Optional[str] = None
    id: Optional[str] = None


class ChatChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = None


class ChatUsage(BaseModel):
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatChoice]
    usage: ChatUsage
