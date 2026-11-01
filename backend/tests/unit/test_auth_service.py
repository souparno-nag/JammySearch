"""Unit tests for credential hashing and session lifetime (FR-048, FR-079, R11).

FR-079 is the requirement under test, and it is written to survive an assumption changing:
credential and session handling must be sound *as though the application were publicly
reachable*, even though this release binds to loopback. So these tests assert the
properties that would matter on a hostile network — stored credentials are not reversible,
sessions stop working when they expire, and a session can be killed on demand — rather
than merely that a sign-in returns True.

Nothing here contacts Redis. `fake_redis` and its `clock` come from `tests/conftest.py`, so
expiry is asserted exactly rather than slept for (Constitution IV forbids both a networked
test and a nondeterministic one).
"""

from datetime import UTC, timedelta

import pytest
from pydantic import SecretStr

import app.users.auth_service as auth
from app.users.auth_service import (
    Session,
    authenticate,
    create_session,
    get_session,
    hash_password,
    invalidate_all_sessions,
    invalidate_session,
    verify_password,
)

PASSWORD = "correct horse battery staple"


# ---------------------------------------------------------------------------
# Credential hashing
# ---------------------------------------------------------------------------


def test_a_hashed_password_verifies_against_itself():
    assert verify_password(PASSWORD, hash_password(PASSWORD)) is True


def test_the_wrong_password_is_rejected():
    assert verify_password("not the password", hash_password(PASSWORD)) is False


def test_the_same_password_hashes_differently_every_time():
    # A random salt per hash. Without it, identical passwords produce identical hashes,
    # which is what makes precomputed-table attacks work.
    assert hash_password(PASSWORD) != hash_password(PASSWORD)


def test_the_stored_hash_does_not_contain_the_password():
    # The point of hashing: whoever reads .env or a backup must not recover the secret.
    assert PASSWORD not in hash_password(PASSWORD)


def test_the_stored_hash_records_the_parameters_used_to_produce_it():
    # Cost parameters are stored with the hash rather than assumed, so they can be raised
    # later without invalidating credentials hashed under the old ones.
    encoded = hash_password(PASSWORD)

    assert encoded.startswith("scrypt$")
    assert len(encoded.split("$")) == 6


@pytest.mark.parametrize(
    "stored",
    [
        "",
        "not-a-hash",
        "scrypt$only$four$fields",
        "scrypt$notanumber$8$1$c2FsdA==$aGFzaA==",
        "bcrypt$16384$8$1$c2FsdA==$aGFzaA==",
        "scrypt$16384$8$1$!!!notbase64!!!$aGFzaA==",
    ],
)
def test_a_malformed_stored_hash_is_rejected_rather_than_raising(stored):
    # A corrupted or hand-edited .env must fail closed as "wrong password", not crash the
    # sign-in path with a traceback that reveals how credentials are stored.
    assert verify_password(PASSWORD, stored) is False


def test_a_long_unicode_password_round_trips():
    secret = "pässwörd " * 40 + "🔐"

    assert verify_password(secret, hash_password(secret)) is True


# ---------------------------------------------------------------------------
# Authentication against the configured credential
# ---------------------------------------------------------------------------


@pytest.fixture
def configured_credential(monkeypatch):
    monkeypatch.setattr(auth.settings, "auth_username", "researcher")
    monkeypatch.setattr(auth.settings, "auth_password_hash", SecretStr(hash_password(PASSWORD)))


def test_the_configured_credential_authenticates(configured_credential):
    assert authenticate("researcher", PASSWORD) is True


def test_a_wrong_password_does_not_authenticate(configured_credential):
    assert authenticate("researcher", "guess") is False


def test_a_wrong_username_does_not_authenticate(configured_credential):
    assert authenticate("someone-else", PASSWORD) is False


def test_authentication_fails_closed_when_no_credential_is_configured(monkeypatch):
    # The state a fresh checkout is in: .env carries no AUTH_PASSWORD_HASH. The dangerous
    # reading of "no password set" is "no password required". It must mean "nobody gets in".
    monkeypatch.setattr(auth.settings, "auth_username", "researcher")
    monkeypatch.setattr(auth.settings, "auth_password_hash", SecretStr(""))

    assert authenticate("researcher", PASSWORD) is False
    assert authenticate("researcher", "") is False


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


async def test_a_new_session_can_be_looked_up_by_its_token(fake_redis):
    session = await create_session(fake_redis, "researcher")

    found = await get_session(fake_redis, session.token)

    assert found is not None
    assert found.username == "researcher"


async def test_an_unknown_token_resolves_to_nothing(fake_redis):
    assert await get_session(fake_redis, "made-up-token") is None


async def test_each_session_gets_a_distinct_unguessable_token(fake_redis):
    first = await create_session(fake_redis, "researcher")
    second = await create_session(fake_redis, "researcher")

    assert first.token != second.token
    # 32 random bytes, URL-safe encoded. Short enough to be a cookie, long enough that
    # guessing is not a strategy.
    assert len(first.token) >= 32


async def test_the_raw_token_is_never_written_to_the_store(fake_redis):
    # FR-079 taken seriously: a leaked Redis dump or a backup must not hand someone a set
    # of live sessions. Only a hash of each token is stored, so what leaks is not replayable.
    session = await create_session(fake_redis, "researcher")

    stored = [key async for key in fake_redis.scan_iter()]
    values = [await fake_redis.get(key) for key in stored]

    assert all(session.token not in key for key in stored)
    assert all(session.token not in (value or "") for value in values)


async def test_a_session_stops_working_once_it_expires(fake_redis, clock):
    session = await create_session(fake_redis, "researcher")

    clock.advance(auth.settings.session_ttl_seconds + 1)

    assert await get_session(fake_redis, session.token) is None


async def test_a_session_still_works_just_before_it_expires(fake_redis, clock):
    # The companion to the test above. Without it, a function returning None always would
    # pass the expiry test and nobody would notice.
    session = await create_session(fake_redis, "researcher")

    clock.advance(auth.settings.session_ttl_seconds - 10)

    assert await get_session(fake_redis, session.token) is not None


async def test_expiry_is_enforced_by_this_module_not_only_by_redis(fake_redis):
    # Defence in depth. Redis TTL is the mechanism that stops expired sessions
    # accumulating, but a stale entry surviving eviction — or a store that lost its TTLs —
    # must not authenticate anybody. The application checks the deadline itself.
    #
    # `now` is passed explicitly rather than slept for: Constitution IV requires wall-clock
    # time to be frozen, and it is what lets this assert the application's own check rather
    # than the fake store's.
    created_at = auth.utc_now()
    session = await create_session(fake_redis, "researcher", now=created_at)
    stored_key = [key async for key in fake_redis.scan_iter()][0]
    value = await fake_redis.get(stored_key)
    await fake_redis.set(stored_key, value)  # re-store with no TTL at all

    after_expiry = created_at + timedelta(seconds=auth.settings.session_ttl_seconds + 1)

    assert await get_session(fake_redis, session.token, now=after_expiry) is None


async def test_the_stored_session_carries_a_ttl(fake_redis):
    await create_session(fake_redis, "researcher")

    stored_key = [key async for key in fake_redis.scan_iter()][0]

    assert await fake_redis.ttl(stored_key) > 0


@pytest.mark.parametrize("empty", ["", None])
async def test_a_missing_token_resolves_to_nothing_without_touching_the_store(fake_redis, empty):
    # A request arriving with no session cookie at all is the common case, not an error.
    assert await get_session(fake_redis, empty) is None
    assert await invalidate_session(fake_redis, empty) is False


async def test_an_unreadable_session_entry_is_discarded_rather_than_raising(fake_redis):
    # If something ever writes a malformed value under a session key, sign-in must degrade
    # to "not signed in" rather than 500 on every authenticated request until it is cleared.
    session = await create_session(fake_redis, "researcher")
    stored_key = [key async for key in fake_redis.scan_iter()][0]
    await fake_redis.set(stored_key, "{not json at all")

    assert await get_session(fake_redis, session.token) is None
    assert await fake_redis.get(stored_key) is None  # and the bad entry is gone


async def test_a_session_entry_missing_its_fields_is_discarded(fake_redis):
    session = await create_session(fake_redis, "researcher")
    stored_key = [key async for key in fake_redis.scan_iter()][0]
    await fake_redis.set(stored_key, '{"username": "researcher"}')

    assert await get_session(fake_redis, session.token) is None


async def test_invalidating_all_sessions_when_there_are_none_is_not_an_error(fake_redis):
    assert await invalidate_all_sessions(fake_redis) == 0


async def test_a_session_can_be_invalidated_before_it_expires(fake_redis):
    # FR-079 requires sessions to be invalidatable, not merely expiring. This is sign-out,
    # and it is the control that matters when a token is believed compromised.
    session = await create_session(fake_redis, "researcher")

    assert await invalidate_session(fake_redis, session.token) is True
    assert await get_session(fake_redis, session.token) is None


async def test_invalidating_an_unknown_session_reports_that_nothing_happened(fake_redis):
    assert await invalidate_session(fake_redis, "made-up-token") is False


async def test_every_session_can_be_invalidated_at_once(fake_redis):
    first = await create_session(fake_redis, "researcher")
    second = await create_session(fake_redis, "researcher")

    assert await invalidate_all_sessions(fake_redis) == 2
    assert await get_session(fake_redis, first.token) is None
    assert await get_session(fake_redis, second.token) is None


async def test_invalidating_all_sessions_leaves_unrelated_keys_alone(fake_redis):
    # Sessions share Redis with the Reddit cache and the rate limiter. A sign-out-everywhere
    # that flushed the database would discard collected material's cache and every counter.
    await fake_redis.set("reddit:listing:designers", "cached")
    await create_session(fake_redis, "researcher")

    await invalidate_all_sessions(fake_redis)

    assert await fake_redis.get("reddit:listing:designers") == "cached"


async def test_session_timestamps_are_utc(fake_redis):
    # Constitution V: stored and transmitted as UTC, localized only at render time.
    session = await create_session(fake_redis, "researcher")

    assert session.created_at.tzinfo is not None
    assert session.created_at.utcoffset() == UTC.utcoffset(None)
    assert session.expires_at > session.created_at


async def test_a_session_does_not_print_its_own_token(fake_redis):
    # Anything that logs a Session — an exception handler, a debug line — must not put a
    # live credential in the log file (FR-079).
    session = await create_session(fake_redis, "researcher")

    assert session.token not in repr(session)


def test_a_session_is_immutable():
    # Guards against a caller extending a session's life by assigning to expires_at
    # instead of going through create_session.
    session = Session(
        token="t",
        username="researcher",
        created_at=auth.utc_now(),
        expires_at=auth.utc_now(),
    )

    with pytest.raises(AttributeError):
        session.username = "someone-else"
