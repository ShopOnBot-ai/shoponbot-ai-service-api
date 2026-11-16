from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    llm_provider: Literal["groq", "ollama"] = "groq"
    groq_model: str = "openai/gpt-oss-120b"
    ollama_model: str = "qwen2.5:3b"
    llm_timeout_s: float = 30

    database_url: str

    ollama_base_url: str
    groq_api_key: str
    qdrant_host: str
    qdrant_port: int
    kafka_bootstrap_server: str
    redis_url: str
    backend_api_url: str
    jwt_secret_key: str
    jwt_algorithm: str

settings = Settings()