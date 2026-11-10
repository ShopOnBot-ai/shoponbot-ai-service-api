from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    llm_provider: str = "ollama"

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