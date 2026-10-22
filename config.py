import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Automated Incident Post-Mortem & Root-Cause Synthesizer"
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

    # LLM Provider Configuration
    DEEPINFRA_API_KEY: str = os.getenv("DEEPINFRA_API_KEY", "")
    DEEPINFRA_MODEL: str = os.getenv("DEEPINFRA_MODEL", "meta-llama/Meta-Llama-3-8B-Instruct")
    DEEPINFRA_BASE_URL: str = os.getenv("DEEPINFRA_BASE_URL", "https://api.deepinfra.com/v1/openai")

    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "mistral")

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")

    LOG_CHUNK_SIZE: int = int(os.getenv("LOG_CHUNK_SIZE", "500"))

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
