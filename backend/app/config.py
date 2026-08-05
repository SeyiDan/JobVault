from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings

_PLACEHOLDER_SECRETS = {"change-me-in-production", "changeme", "secret", ""}


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://jobvault:jobvault@db:5432/jobvault"
    # No default: the app must refuse to start rather than sign tokens with a
    # guessable key (CWE-798). Generate one with:
    #   python -c "import secrets; print(secrets.token_urlsafe(48))"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    # 60 minutes, down from 24 hours. There is no refresh or revocation, so a
    # leaked token is valid until it expires; keep that window short.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    class Config:
        env_file = ".env"

    @field_validator("SECRET_KEY")
    @classmethod
    def _reject_weak_secret(cls, v: str) -> str:
        if v in _PLACEHOLDER_SECRETS:
            raise ValueError(
                "SECRET_KEY is a known placeholder. Generate one with "
                '`python -c "import secrets; print(secrets.token_urlsafe(48))"`'
            )
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
