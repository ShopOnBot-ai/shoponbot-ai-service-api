from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama

from app.core.config import settings


def build_llm():
    provider = settings.llm_provider

    if provider == "groq":
        if not settings.groq_api_key:
            raise ValueError("Groq provider selected but GROQ_API_KEY is not set.")
        return ChatGroq(
            model=settings.groq_model,
            api_key=settings.groq_api_key,
            temperature=0,
            reasoning_effort="low",
            timeout=settings.llm_timeout_s,
            max_retries=2,
        )
    elif provider == "ollama":
        return ChatOllama(
            model="qwen2.5:3b",
            base_url=settings.ollama_base_url,
            temperature=0,
            keep_alive="30m",
        )
    raise ValueError(f"Unknown LLM provider: {provider}")

llm_chat_engine = build_llm()