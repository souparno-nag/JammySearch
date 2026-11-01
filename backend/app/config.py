"""Application settings.

This is the only module permitted to read secrets from the environment
(Constitution, Technology and Data Constraints). Every other module that needs
a credential or a connection string imports `settings` from here rather than
calling `os.getenv` directly.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Every setting the application reads.

    Secrets are typed `SecretStr` (FR-079). Rendering the object — `repr`, `str`, a log line,
    a dump — shows `**********` in their place, so an accidental `logger.debug(settings)`
    leaks nothing. Code that needs the value calls `.get_secret_value()` at the point of use,
    which keeps every place a secret is unwrapped searchable.
    """

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Reddit — consumed only by backend/app/reddit/ (Constitution I)
    reddit_client_id: str = Field(alias="REDDIT_CLIENT_ID")
    reddit_client_secret: SecretStr = Field(alias="REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = Field(alias="REDDIT_USER_AGENT")

    # Database — async driver required by Constitution VI. A secret because the connection
    # string carries the database password.
    database_url: SecretStr = Field(alias="DATABASE_URL")

    # Redis — cache and Celery broker
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # LLM — Groq for completions, local sentence-transformers for embeddings (R1).
    # Model identifiers are pinned here explicitly; a floating alias is prohibited
    # by Constitution VII.
    groq_api_key: SecretStr = Field(alias="GROQ_API_KEY")
    groq_model: str = Field(alias="GROQ_MODEL")
    embedding_model_name: str = Field(alias="EMBEDDING_MODEL_NAME")

    # Deployment exposure (FR-078). Binding beyond loopback requires this explicit opt-in;
    # the startup bind guard in app/main.py reads this flag rather than the raw env var.
    allow_remote_exposure: bool = Field(default=False, alias="ALLOW_REMOTE_EXPOSURE")

    # Sign-in (FR-048, R11). Single user, credentials in configuration, no self-service
    # registration. `auth_password_hash` holds a *hash* produced by
    # `app.users.auth_service.hash_password` — never a plaintext password (FR-079). It
    # defaults to empty, and an empty value means nobody can sign in: "no credential
    # configured" must fail closed rather than read as "no credential required". The default
    # is spelled `SecretStr("")` because pydantic does not validate defaults: a bare `""`
    # would stay a plain `str` and break every caller that unwraps it.
    auth_username: str = Field(default="researcher", alias="AUTH_USERNAME")
    auth_password_hash: SecretStr = Field(default=SecretStr(""), alias="AUTH_PASSWORD_HASH")

    # How long a session stays valid. Twelve hours: long enough to cover a working day
    # without re-authenticating, short enough that a forgotten session is not indefinite.
    session_ttl_seconds: int = Field(default=43_200, alias="SESSION_TTL_SECONDS")

    # Default request-rate allowance for endpoints that can trigger a paid call (FR-080).
    # Generous for one person working normally, low enough to stop a runaway loop from
    # exhausting a provider's free tier before anyone notices.
    rate_limit_requests: int = Field(default=60, alias="RATE_LIMIT_REQUESTS")
    rate_limit_window_seconds: int = Field(default=60, alias="RATE_LIMIT_WINDOW_SECONDS")

    # Sign-in attempt allowance, kept separate from the paid-call defaults above because the
    # profile is different: signing in costs nothing, but it is the one endpoint an
    # unauthenticated caller can reach repeatedly. Ten attempts per five minutes is
    # unremarkable for someone mistyping a password and useless for guessing one.
    signin_rate_limit_requests: int = Field(default=10, alias="SIGNIN_RATE_LIMIT_REQUESTS")
    signin_rate_limit_window_seconds: int = Field(
        default=300, alias="SIGNIN_RATE_LIMIT_WINDOW_SECONDS"
    )

    # The interface the application is expected to bind. Consulted by the same guard when
    # the server is started programmatically, i.e. with no uvicorn `--host` on the command
    # line to read. The default is what makes loopback-only the behaviour you get by doing
    # nothing, which is the whole point of FR-078.
    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide Settings instance, constructed once and cached."""
    return Settings()


settings = get_settings()
