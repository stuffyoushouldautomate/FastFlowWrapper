from pydantic import BaseModel
from typing import Optional


class FlowiseChatflow(BaseModel):
    id: str
    name: Optional[str] = None
    flowData: Optional[str] = None
    deployed: Optional[bool] = None
    isPublic: Optional[bool] = None
    apikeyid: Optional[str] = None
    chatbotConfig: Optional[str] = None
    apiConfig: Optional[str] = None
    analytic: Optional[str] = None
    speechToText: Optional[str] = None
    category: Optional[str] = None
    type: Optional[str] = None
    createdDate: Optional[str] = None
    updatedDate: Optional[str] = None
