from langchain_ollama import ChatOllama

from app.core.config import settings

llm_chat_engine = ChatOllama(
    model="llama3.2:1b",
    base_url=settings.ollama_base_url,
    temperature=0
)
