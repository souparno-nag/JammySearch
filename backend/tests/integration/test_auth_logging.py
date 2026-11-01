"""Integration tests asserting the sign-in path never logs a credential (FR-079).

The session routes already log carefully ("sign-in refused", with nothing attached). These
tests exist so that stays true: a later "helpful" log line that includes the attempted
password, the configured hash, or the issued session token fails here instead of shipping.

Every record captured during the request is checked, from every logger and at every level,
including its arguments and `extra` fields, because a secret passed as structured context
leaks just as surely as one in the message text.

They drive the real application, as `test_auth_routes.py` does, because the request crosses
the users router, the limiter, and the error middleware, and any of the three could log.
"""

import logging

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.common.redis import get_redis
from app.config import settings
from app.dependencies import SESSION_COOKIE_NAME
from app.main import create_app
from app.users.auth_service import hash_password

PASSWORD = "correct-horse-battery-staple"
PASSWORD_HASH = hash_password(PASSWORD)
SIGN_IN = "/auth/session"


@pytest.fixture
def client(fake_redis, monkeypatch):
    monkeypatch.setattr(settings, "auth_username", "researcher")
    monkeypatch.setattr(settings, "auth_password_hash", SecretStr(PASSWORD_HASH))
    built = create_app()
    built.dependency_overrides[get_redis] = lambda: fake_redis
    return TestClient(built)


def everything_logged(caplog) -> str:
    """Every captured record rendered in full: message, arguments, and extra fields."""
    return "\n".join(f"{record.getMessage()} {record.__dict__!r}" for record in caplog.records)


def test_a_refused_sign_in_logs_neither_the_attempt_nor_the_stored_hash(client, caplog):
    caplog.set_level(logging.DEBUG)
    attempted = "a-guessed-password-sentinel"

    response = client.post(SIGN_IN, json={"username": "researcher", "password": attempted})

    assert response.status_code == 401
    logged = everything_logged(caplog)
    assert attempted not in logged
    assert PASSWORD_HASH not in logged


def test_a_successful_sign_in_logs_neither_the_password_nor_the_session_token(client, caplog):
    caplog.set_level(logging.DEBUG)

    response = client.post(SIGN_IN, json={"username": "researcher", "password": PASSWORD})

    assert response.status_code == 200
    token = response.cookies[SESSION_COOKIE_NAME]
    logged = everything_logged(caplog)
    assert PASSWORD not in logged
    assert token not in logged
