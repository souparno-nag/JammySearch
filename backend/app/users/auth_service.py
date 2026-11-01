"""Credential verification and session lifetime.

This is a single-user product (R11): the credential lives in configuration, there is no
self-service registration, and no query is scoped by tenant. Sign-in exists to protect one
person's data, not to separate accounts.

Everything here is built to the standard FR-079 sets — sound *as though the application
were publicly reachable* — because this release binds to loopback only by deployment
choice, and that choice must not be load-bearing. The measures that live in application
code are cheap now and are a migration later, so they are built now. The ones that live in
the deployment (transport security, abuse protection, monitoring) are deliberately absent
per FR-081.

Three properties are worth stating outright:

- **The stored credential is a scrypt hash**, not a password. `hashlib.scrypt` is a
  memory-hard key derivation function in the standard library, so this needs no dependency
  outside the constitution's committed stack.
- **Only a hash of each session token is stored.** A leaked Redis dump or backup therefore
  yields no usable session. The token itself is 32 random bytes, so SHA-256 is the right
  digest here — a slow KDF exists to protect low-entropy secrets, and this is not one.
- **Expiry is checked here, not merely delegated to Redis.** The TTL stops expired
  sessions accumulating; this module decides whether a session is valid.

Sessions live in Redis because it provides expiry and invalidation natively, which are the
two properties FR-079 requires. The constitution's Technology and Data Constraints section
names session entries as ephemeral operational state, exempt from the rule that no durable
data may exist only in Redis: that rule protects the collected corpus, which cannot be
re-fetched, whereas losing every session costs exactly one sign-in. The reasoning behind
the exemption is recorded in `docs/tasks/T020.md`.

External systems touched: Redis.
"""

import base64
import hashlib
import json
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis

from app.config import settings

logger = logging.getLogger(__name__)

# Namespace for session keys. Redis is shared with the Reddit cache and the rate limiter,
# so "invalidate every session" must be able to select sessions and nothing else.
SESSION_KEY_PREFIX = "session:"
SESSION_KEY_PATTERN = f"{SESSION_KEY_PREFIX}*"

# scrypt cost parameters. Stored inside each encoded hash rather than assumed, so raising
# them later does not invalidate credentials hashed under the old ones.
SCRYPT_N = 2**14  # CPU/memory cost — the dominant term, ~16 MiB at r=8
SCRYPT_R = 8  # block size
SCRYPT_P = 1  # parallelism
SCRYPT_DKLEN = 32
SALT_BYTES = 16
TOKEN_BYTES = 32

ALGORITHM = "scrypt"
ENCODED_FIELD_COUNT = 6


def utc_now() -> datetime:
    """Return the current instant in UTC.

    A single seam for the clock. Constitution V fixes UTC as the storage and transport
    representation, and Constitution IV requires tests to freeze time — which they do by
    passing `now` explicitly to the functions below rather than by patching this.
    """
    return datetime.now(UTC)


@dataclass(frozen=True)
class Session:
    """A signed-in session. Immutable, so its lifetime cannot be extended by assignment."""

    token: str
    username: str
    created_at: datetime
    expires_at: datetime

    def __repr__(self) -> str:
        # The token is a live credential. A Session reaching a log line through an
        # exception handler or a debug statement must not carry it (FR-079).
        return (
            f"Session(token='<redacted>', username={self.username!r}, "
            f"created_at={self.created_at.isoformat()}, "
            f"expires_at={self.expires_at.isoformat()})"
        )


# ---------------------------------------------------------------------------
# Credential hashing
# ---------------------------------------------------------------------------


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    """Return an encoded scrypt hash of `password`, safe to store in configuration.

    The encoding is `scrypt$n$r$p$salt$hash`, with salt and hash base64-encoded. The cost
    parameters travel with the hash so they can be raised later without invalidating
    existing credentials.

    `salt` is a parameter only so a caller can reproduce a known hash; leave it unset and a
    fresh random salt is generated, which is what makes two hashes of the same password
    differ. Touches no external system.
    """
    salt = salt if salt is not None else secrets.token_bytes(SALT_BYTES)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    return "$".join(
        [
            ALGORITHM,
            str(SCRYPT_N),
            str(SCRYPT_R),
            str(SCRYPT_P),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(derived).decode("ascii"),
        ]
    )


def verify_password(password: str, encoded: str) -> bool:
    """Return whether `password` produces `encoded`.

    Any malformed, empty, or foreign-algorithm value returns `False` rather than raising: a
    hand-edited or corrupted `.env` must fail closed as "wrong password", never with a
    traceback describing how credentials are stored. Comparison is constant-time, so the
    time taken does not reveal how much of the hash matched.

    Touches no external system.
    """
    try:
        algorithm, raw_n, raw_r, raw_p, raw_salt, raw_hash = encoded.split("$")
        if algorithm != ALGORITHM:
            return False
        salt = base64.b64decode(raw_salt, validate=True)
        expected = base64.b64decode(raw_hash, validate=True)
        candidate = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(raw_n),
            r=int(raw_r),
            p=int(raw_p),
            dklen=len(expected),
        )
    except (ValueError, TypeError, MemoryError):
        # ValueError covers the wrong field count, non-numeric parameters, and invalid
        # base64; MemoryError covers absurd cost parameters in a tampered value.
        return False
    return secrets.compare_digest(candidate, expected)


def authenticate(username: str, password: str) -> bool:
    """Return whether the supplied credential matches the configured one.

    Reads `settings.auth_username` and `settings.auth_password_hash`. An unconfigured
    password hash denies everyone — "no credential configured" must never be read as "no
    credential required", which is the state a fresh checkout is in.

    Touches no external system.
    """
    stored = settings.auth_password_hash.get_secret_value()
    if not stored:
        logger.warning(
            "sign-in refused: no credential is configured. Set AUTH_PASSWORD_HASH in .env "
            "to a value produced by app.users.auth_service.hash_password."
        )
        return False
    # Both halves are evaluated before the result is combined, so the time taken does not
    # reveal whether the username alone was correct.
    username_matches = secrets.compare_digest(username, settings.auth_username)
    password_matches = verify_password(password, stored)
    return username_matches and password_matches


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


def _session_key(token: str) -> str:
    """Return the Redis key for a token, derived by digest so the token itself is never stored."""
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"{SESSION_KEY_PREFIX}{digest}"


async def create_session(redis: Redis, username: str, *, now: datetime | None = None) -> Session:
    """Create a session and return it, including the token to hand to the client.

    The returned token is the only copy in existence — the store holds a digest of it. The
    entry is written with a Redis TTL matching the session's own deadline, so expired
    sessions are reclaimed rather than accumulating.

    External systems touched: Redis.
    """
    moment = now or utc_now()
    ttl = settings.session_ttl_seconds
    session = Session(
        token=secrets.token_urlsafe(TOKEN_BYTES),
        username=username,
        created_at=moment,
        expires_at=moment + timedelta(seconds=ttl),
    )
    payload = json.dumps(
        {
            "username": session.username,
            "created_at": session.created_at.isoformat(),
            "expires_at": session.expires_at.isoformat(),
        }
    )
    await redis.set(_session_key(session.token), payload, ex=ttl)
    return session


async def get_session(redis: Redis, token: str, *, now: datetime | None = None) -> Session | None:
    """Return the session for `token`, or `None` if it is unknown, malformed, or expired.

    The expiry check is performed here rather than left to Redis. The TTL is what keeps the
    store tidy; this is what decides whether a session authenticates, so an entry that
    outlived its TTL for any reason still fails. An expired entry found here is deleted on
    the way out.

    External systems touched: Redis.
    """
    if not token:
        return None
    key = _session_key(token)
    raw = await redis.get(key)
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
        username = payload["username"]
        created_at = datetime.fromisoformat(payload["created_at"])
        expires_at = datetime.fromisoformat(payload["expires_at"])
    except (ValueError, TypeError, KeyError):
        # An unreadable entry is not a valid session. Drop it rather than failing requests.
        logger.warning("discarding an unreadable session entry")
        await redis.delete(key)
        return None
    if (now or utc_now()) >= expires_at:
        await redis.delete(key)
        return None
    return Session(
        token=token,
        username=username,
        created_at=created_at,
        expires_at=expires_at,
    )


async def invalidate_session(redis: Redis, token: str) -> bool:
    """End one session immediately, returning whether it existed.

    This is sign-out, and the control that matters when a token is believed compromised.
    FR-079 requires sessions to be invalidatable, not merely to expire eventually.

    External systems touched: Redis.
    """
    if not token:
        return False
    return await redis.delete(_session_key(token)) > 0


async def invalidate_all_sessions(redis: Redis) -> int:
    """End every session, returning how many were ended.

    Selects on the session key prefix rather than clearing the database: Redis also holds
    the Reddit cache and the rate-limit counters, and discarding those would cost real
    Reddit quota to rebuild.

    External systems touched: Redis.
    """
    keys = [key async for key in redis.scan_iter(match=SESSION_KEY_PATTERN)]
    if not keys:
        return 0
    return await redis.delete(*keys)
