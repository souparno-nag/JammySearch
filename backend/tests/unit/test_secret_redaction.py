"""Unit tests asserting configuration never renders its secrets (FR-079).

FR-079 requires that secrets "never appear in responses, logs, or anything the client can
read". The most likely way that rule breaks is not a deliberate log of a password; it is an
innocent `logger.debug(settings)` or an f-string that interpolates the settings object while
chasing some other bug. Every secret therefore has to be unreadable *by default* when the
object is rendered, and readable only through an explicit `get_secret_value()` at the point
where it is actually used.

`Settings` is built here with sentinel values and `_env_file=None`, so the tests depend on
neither a local `.env` nor whatever happens to be in the environment.
"""

import pytest

from app.config import Settings

SECRETS = {
    "REDDIT_CLIENT_SECRET": "reddit-secret-sentinel",
    "GROQ_API_KEY": "groq-key-sentinel",
    "DATABASE_URL": "postgresql+asyncpg://user:db-password-sentinel@localhost/jammysearch",
    "AUTH_PASSWORD_HASH": "scrypt$hash-sentinel",
}

# The fragment of each secret that must never be printed. For the database URL that is the
# password inside it, not the whole connection string.
SENTINELS = [
    "reddit-secret-sentinel",
    "groq-key-sentinel",
    "db-password-sentinel",
    "hash-sentinel",
]


def build_settings() -> Settings:
    return Settings(
        _env_file=None,
        REDDIT_CLIENT_ID="client-id",
        REDDIT_USER_AGENT="jammysearch-tests",
        GROQ_MODEL="pinned-model",
        EMBEDDING_MODEL_NAME="local-embedding-model",
        **SECRETS,
    )


@pytest.mark.parametrize(
    "render",
    [repr, str, lambda s: s.model_dump_json(), lambda s: str(s.model_dump())],
    ids=["repr", "str", "model_dump_json", "model_dump"],
)
def test_rendering_settings_never_reveals_a_secret(render):
    rendered = render(build_settings())

    for sentinel in SENTINELS:
        assert sentinel not in rendered


def test_each_secret_is_still_readable_where_it_is_used():
    # Redaction must not make the secret unusable: the code that needs it unwraps it
    # explicitly, and gets the exact configured value back.
    settings = build_settings()

    assert settings.reddit_client_secret.get_secret_value() == SECRETS["REDDIT_CLIENT_SECRET"]
    assert settings.groq_api_key.get_secret_value() == SECRETS["GROQ_API_KEY"]
    assert settings.database_url.get_secret_value() == SECRETS["DATABASE_URL"]
    assert settings.auth_password_hash.get_secret_value() == SECRETS["AUTH_PASSWORD_HASH"]


def test_an_unconfigured_password_hash_is_an_empty_secret():
    # A fresh checkout has no AUTH_PASSWORD_HASH. The default must still be a secret, so
    # the fail-closed check in auth_service reads it the same way as a configured one.
    settings = Settings(
        _env_file=None,
        **{k: v for k, v in SECRETS.items() if k != "AUTH_PASSWORD_HASH"},
        REDDIT_CLIENT_ID="client-id",
        REDDIT_USER_AGENT="jammysearch-tests",
        GROQ_MODEL="pinned-model",
        EMBEDDING_MODEL_NAME="local-embedding-model",
    )

    assert settings.auth_password_hash.get_secret_value() == ""
