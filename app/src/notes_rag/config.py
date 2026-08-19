from functools import lru_cache
from typing import Self

from pydantic import Field, HttpUrl, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_prefix="NOTES_",
        extra="ignore",
        frozen=True,
    )

    database_url: str
    migration_database_url: str
    session_secret: str = Field(min_length=32)
    csrf_secret: str = Field(min_length=32)
    cookie_secure: bool = False
    allowed_origin: HttpUrl = HttpUrl("http://localhost:8000")
    ollama_url: HttpUrl = HttpUrl("http://ollama:11434")
    embedding_model: str = "embeddinggemma:300m"
    embedding_model_digest: str
    generation_model: str = "llama3:latest"
    generation_model_id: str = "365c0bd3c000"
    retrieval_limit: int = Field(default=5, ge=1, le=10)
    retrieval_minimum_similarity: float = Field(default=0.55, ge=0, le=1)
    worker_poll_seconds: float = Field(default=1, gt=0, le=60)
    worker_lease_seconds: int = Field(default=60, ge=10, le=600)
    session_lifetime_seconds: int = Field(default=86_400, ge=300)

    @model_validator(mode="after")
    def validate_security_boundaries(self) -> Self:
        placeholders = ("change_me", "changeme", "replace_me")
        for value in (self.session_secret, self.csrf_secret, self.embedding_model_digest):
            if any(marker in value.casefold() for marker in placeholders):
                raise ValueError("placeholder secrets and model digests are not allowed")
        if self.database_url == self.migration_database_url:
            raise ValueError("runtime and migration database roles must use distinct URLs")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
