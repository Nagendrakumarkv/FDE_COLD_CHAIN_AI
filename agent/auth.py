"""Admin authentication: bcrypt verification and login throttling."""

import logging
import threading
import time

import bcrypt

from tools import chat_store

logger = logging.getLogger(__name__)

# bcrypt only uses the first 72 bytes, and newer versions reject longer input.
MAX_PASSWORD_BYTES = 72
MAX_USERNAME_LENGTH = 100

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 300
MAX_TRACKED_USERNAMES = 1000

SESSION_MAX_SECONDS = 8 * 60 * 60

# Verified when the username does not exist, so timing does not reveal it.
_DUMMY_HASH = bcrypt.hashpw(b"not-a-real-password", bcrypt.gensalt())

_failures: dict[str, list[float]] = {}
_lock = threading.Lock()


class LoginLocked(Exception):
    """Too many failed attempts for this username."""

    def __init__(self, retry_after_seconds: int):
        super().__init__("Too many failed login attempts.")
        self.retry_after_seconds = retry_after_seconds


def hash_password(password: str) -> str:
    """Return a bcrypt hash for a plain-text password."""
    encoded = password.encode("utf-8")

    if not encoded or len(encoded) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Password must be 1 to {MAX_PASSWORD_BYTES} bytes long."
        )

    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, stored_hash: str) -> bool:
    """Check a plain-text password against a bcrypt hash."""
    encoded = password.encode("utf-8")

    if not encoded or len(encoded) > MAX_PASSWORD_BYTES:
        return False

    try:
        return bcrypt.checkpw(encoded, stored_hash.encode("utf-8"))
    except (ValueError, TypeError):
        # Malformed stored hash: treat as a failed login, never crash.
        logger.error("Stored password hash is not a valid bcrypt hash.")
        return False


def _prune(key, now):
    recent = [t for t in _failures.get(key, []) if now - t < LOCKOUT_SECONDS]

    if recent:
        _failures[key] = recent
    else:
        _failures.pop(key, None)

    return recent


def _check_lock(key, now):
    with _lock:
        recent = _prune(key, now)

        if len(recent) >= MAX_FAILED_ATTEMPTS:
            wait = int(recent[0] + LOCKOUT_SECONDS - now) + 1
            raise LoginLocked(max(wait, 1))


def _record_failure(key, now):
    with _lock:
        if (
            key not in _failures
            and len(_failures) >= MAX_TRACKED_USERNAMES
        ):
            for stale in list(_failures):
                _prune(stale, now)

        if key in _failures or len(_failures) < MAX_TRACKED_USERNAMES:
            _failures.setdefault(key, []).append(now)


def _clear_failures(key):
    with _lock:
        _failures.pop(key, None)


def reset_throttle():
    """Clear all failure records (used by tests)."""
    with _lock:
        _failures.clear()


def authenticate(username, password, lookup=None, clock=time.monotonic):
    """Return {"id", "username"} for valid credentials, else None.

    Raises LoginLocked when the username has too many recent failures.
    The caller must show one generic message for any None result.
    """
    lookup = lookup or chat_store.get_admin_by_username

    if not isinstance(username, str) or not isinstance(password, str):
        return None

    username = username.strip()

    if not username or len(username) > MAX_USERNAME_LENGTH:
        return None

    key = username.lower()
    now = clock()

    _check_lock(key, now)

    admin = lookup(username)

    if admin is None:
        # Spend the same time as a real check.
        bcrypt.checkpw(b"not-a-real-password", _DUMMY_HASH)
        _record_failure(key, now)
        return None

    if not verify_password(password, admin["password_hash"]):
        _record_failure(key, now)
        return None

    _clear_failures(key)

    return {"id": admin["id"], "username": admin["username"]}
