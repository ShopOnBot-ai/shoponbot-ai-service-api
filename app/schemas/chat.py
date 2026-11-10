from pydantic import BaseModel


class ChatMessageRequest(BaseModel):
    prompt: str
    stream: bool = False