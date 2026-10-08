from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )

    ollama_base_url: str
    qdrant_host: str
    qdrant_port: int
    kafka_bootstrap_server: str
    redis_url: str

settings = Settings()