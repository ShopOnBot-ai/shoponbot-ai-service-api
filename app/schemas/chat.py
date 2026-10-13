from pydantic import BaseModel

class ChatMessageRequest(BaseModel):
    prompt: str
    thread_id: str