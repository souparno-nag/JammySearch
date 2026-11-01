"""Integration tests for the session endpoints (FR-048, FR-079).

These are the routes contracted by `contracts/rest-api.md` under "Sessions": sign in, sign
out, and read the current session. They are integration rather than unit tests because a
single request crosses four modules — the users router, `app/dependencies.py`, the limiter in
`app/common/limits.py`, and the error middleware — and Constitution IV requires integration
tests for anything crossing a module boundary.

They drive the **real application** from `create_app()` rather than a hand-built app with the
router attached, because half of what can go wrong here is wiring: a router that is never
registered, or registered under a path the contract does not name, passes every unit test.

Most of the assertions below are about what a failure must *not* reveal. That is deliberate —
the success path of a sign-in endpoint is the easy half.

Redis is the in-memory fake from `tests/conftest.py`; no test contacts a real service.
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.common.redis import get_redis
from app.config import settings
from app.dependencies import SESSION_COOKIE_NAME
from app.main import create_app
from app.users.auth_service import hash_password

PASSWORD = "correct-horse-battery-staple"

# Hashed once for the whole module. `hash_password` is deliberately slow (scrypt at ~16 MiB),
# so hashing per test would make the suite pay for it repeatedly to no purpose.
PASSWORD_HASH = hash_password(PASSWORD)

SIGN_IN = "/auth/session"


@pytest.fixture
def configured(monkeypatch):
    """Configure the single credential this deployment accepts.

    Patched onto `settings` rather than read from `.env`, so the suite passes on a checkout
    with no credential configured — which is the state a fresh clone is in.
    """
    monkeypatch.setattr(settings, "auth_username", "researcher")
    monkeypatch.setattr(settings, "auth_password_hash", SecretStr(PASSWORD_HASH))


@pytest.fixture
def client(fake_redis, configured):
    built = create_app()
    built.dependency_overrides[get_redis] = lambda: fake_redis
    return TestClient(built)


def sign_in(client, username="researcher", password=PASSWORD):
    return client.post(SIGN_IN, json={"username": username, "password": password})


# ---------------------------------------------------------------------------
# Signing in
# ---------------------------------------------------------------------------


def test_signing_in_with_the_configured_credential_succeeds(client):
    response = sign_in(client)

    assert response.status_code == 200
    assert response.json()["username"] == "researcher"


def test_signing_in_reports_when_the_session_expires(client):
    # Constitution V fixes UTC ISO 8601 on the wire, so a client can show the user how long
    # they have without guessing the server's TTL. Asserted by parsing rather than by matching
    # a suffix: "Z" and "+00:00" are both valid UTC, and which one Pydantic emits is not the
    # property worth pinning.
    expires_at = datetime.fromisoformat(sign_in(client).json()["expires_at"])

    assert expires_at.utcoffset() == timedelta(0)


def test_signing_in_sets_the_session_cookie(client):
    response = sign_in(client)

    assert response.cookies[SESSION_COOKIE_NAME]


def test_the_session_cookie_is_not_readable_by_page_scripts(client):
    # FR-079: secrets must not appear in anything the client can read. HttpOnly is the whole
    # reason this is a cookie rather than a bearer token in the response body.
    header = sign_in(client).headers["set-cookie"]

    assert "HttpOnly" in header


def test_the_session_cookie_is_not_sent_on_cross_site_requests(client):
    header = sign_in(client).headers["set-cookie"].lower()

    assert "samesite=lax" in header


def test_the_session_token_is_never_in_the_response_body(client):
    # The token exists in exactly one place a client can hold it: the HttpOnly cookie.
    response = sign_in(client)
    token = response.cookies[SESSION_COOKIE_NAME]

    assert token not in response.text


# ---------------------------------------------------------------------------
# Refusing to sign in
# ---------------------------------------------------------------------------


def test_a_wrong_password_is_refused(client):
    response = sign_in(client, password="not-the-password")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_an_unknown_username_is_refused(client):
    response = sign_in(client, username="somebody-else")

    assert response.status_code == 401


def test_an_unconfigured_credential_refuses_everyone(client, monkeypatch):
    # A deployment that has never set AUTH_PASSWORD_HASH must fail closed. "No credential
    # configured" must never read as "no credential required".
    monkeypatch.setattr(settings, "auth_password_hash", SecretStr(""))

    assert sign_in(client).status_code == 401


def test_every_refusal_is_indistinguishable(client, monkeypatch):
    # The property that matters: a caller cannot learn which usernames exist, nor that this
    # deployment has no credential set, by comparing responses.
    wrong_password = sign_in(client, password="not-the-password")
    unknown_username = sign_in(client, username="somebody-else")
    monkeypatch.setattr(settings, "auth_password_hash", SecretStr(""))
    unconfigured = sign_in(client)

    responses = [wrong_password, unknown_username, unconfigured]

    assert {r.status_code for r in responses} == {401}
    assert len({r.text for r in responses}) == 1


def test_a_refusal_does_not_describe_the_authentication_scheme(client):
    # FR-052: say what to do next, not how credentials are stored.
    message = sign_in(client, password="wrong").json()["error"]["message"].lower()

    for leak in ("redis", "scrypt", "hash", "cookie", "token"):
        assert leak not in message


def test_a_refusal_sets_no_cookie(client):
    response = sign_in(client, password="wrong")

    assert SESSION_COOKIE_NAME not in response.cookies


def test_a_malformed_request_is_rejected_as_invalid_not_unauthorized(client):
    # A missing field is the caller's mistake, not a failed credential; conflating them would
    # hide a client bug behind a 401 forever.
    response = client.post(SIGN_IN, json={"username": "researcher"})

    assert response.status_code == 422


def test_sign_in_attempts_are_rate_limited(client, monkeypatch):
    # FR-080: the limit is a control in its own right. Keyed on the calling client, since at
    # sign-in there is no session to key on.
    monkeypatch.setattr(settings, "signin_rate_limit_requests", 2)

    for _ in range(2):
        assert sign_in(client, password="wrong").status_code == 401
    response = sign_in(client, password="wrong")

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    assert response.json()["error"]["details"]["retry_after_seconds"] >= 0


def test_the_rate_limit_applies_to_successful_attempts_too(client, monkeypatch):
    # Counted regardless of outcome. A limiter that only counts failures is trivially evaded
    # by a caller who does not care about the outcome.
    monkeypatch.setattr(settings, "signin_rate_limit_requests", 1)
    assert sign_in(client).status_code == 200

    assert sign_in(client).status_code == 429


# ---------------------------------------------------------------------------
# Reading the current session
# ---------------------------------------------------------------------------


def test_the_current_session_is_reported_after_signing_in(client):
    sign_in(client)

    response = client.get(SIGN_IN)

    assert response.status_code == 200
    assert response.json()["username"] == "researcher"
    assert response.json()["expires_at"]


def test_reading_the_current_session_without_one_is_refused(client):
    # This is what lets a cold page load ask "am I signed in?" without firing a doomed
    # request at an unrelated data route.
    response = client.get(SIGN_IN)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_reading_the_current_session_does_not_return_the_token(client):
    token = sign_in(client).cookies[SESSION_COOKIE_NAME]

    assert token not in client.get(SIGN_IN).text


# ---------------------------------------------------------------------------
# Signing out
# ---------------------------------------------------------------------------


def test_signing_out_ends_the_session_immediately(client):
    sign_in(client)

    assert client.delete(SIGN_IN).status_code == 204
    # The session must stop working on the very next request, not when its TTL lapses.
    assert client.get(SIGN_IN).status_code == 401


def test_signing_out_clears_the_cookie(client):
    sign_in(client)

    response = client.delete(SIGN_IN)

    # Leaving a dead token in the browser would have it resent on every later request.
    assert 'jammysearch_session=""' in response.headers["set-cookie"]


def test_signing_out_without_a_session_still_succeeds(client):
    # 204 whether or not the token was live. A 404 for an unknown token would confirm which
    # tokens are real, turning sign-out into an oracle.
    assert client.delete(SIGN_IN).status_code == 204


def test_signing_out_twice_still_succeeds(client):
    sign_in(client)

    assert client.delete(SIGN_IN).status_code == 204
    assert client.delete(SIGN_IN).status_code == 204


async def test_signing_out_leaves_other_redis_state_alone(client, fake_redis):
    # invalidate_session must delete one key, not clear the database: Redis also holds the
    # Reddit cache, which costs real quota to rebuild.
    cache_key = "cache:subreddit:python"
    await fake_redis.set(cache_key, "cached listing")
    sign_in(client)

    client.delete(SIGN_IN)

    assert await fake_redis.get(cache_key) == "cached listing"
