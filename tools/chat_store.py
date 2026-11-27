"""Admin accounts, conversations and messages stored in PostgreSQL (Neon).

Every function that touches a conversation takes the owning admin's ID and
filters on it, so one admin can never read, rename or delete another
admin's conversations. All values are passed as bound parameters.
"""

import logging
import re
from datetime import datetime, timezone

from sqlalchemy import text

logger = logging.getLogger(__name__)

TITLE_MAX_LENGTH = 60
STORED_TITLE_MAX_LENGTH = 200
VALID_ROLES = ("user", "assistant")

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS admin_users (
        id BIGSERIAL PRIMARY KEY,
        username VARCHAR(100) NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id BIGSERIAL PRIMARY KEY,
        admin_user_id BIGINT NOT NULL
            REFERENCES admin_users (id) ON DELETE CASCADE,
        title VARCHAR(200) NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversation_messages (
        id BIGSERIAL PRIMARY KEY,
        conversation_id BIGINT NOT NULL
            REFERENCES conversations (id) ON DELETE CASCADE,
        role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
        content TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_conversations_admin_updated
    ON conversations (admin_user_id, updated_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON conversation_messages (conversation_id, id)
    """,
]


def _now():
    return datetime.now(timezone.utc)


def _get_engine(engine=None):
    """Return the given engine, else the shared application engine."""
    if engine is not None:
        return engine

    from tools.sql_tool import engine as default_engine

    return default_engine


def ensure_schema(engine=None):
    """Create the admin and chat tables if they do not exist."""
    engine = _get_engine(engine)

    for statement in SCHEMA_STATEMENTS:
        with engine.begin() as connection:
            connection.execute(text(statement))


def make_title(first_message: str) -> str:
    """Build a short conversation title from the first user message."""
    title = re.sub(r"\s+", " ", str(first_message)).strip()

    if not title:
        return "New conversation"

    if len(title) > TITLE_MAX_LENGTH:
        title = title[: TITLE_MAX_LENGTH - 3].rstrip() + "..."

    return title


# --------------------------------------------------
# Admin accounts
# --------------------------------------------------
def get_admin_by_username(username: str, engine=None):
    """Return {id, username, password_hash} or None. Lookup ignores case."""
    engine = _get_engine(engine)

    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT id, username, password_hash FROM admin_users "
                "WHERE lower(username) = :username"
            ),
            {"username": str(username).strip().lower()},
        ).first()

    return dict(row._mapping) if row else None


def create_admin(username: str, password_hash: str, engine=None) -> int:
    """Insert an admin account and return its ID."""
    engine = _get_engine(engine)

    with engine.begin() as connection:
        return connection.execute(
            text(
                "INSERT INTO admin_users (username, password_hash, "
                "created_at) VALUES (:username, :password_hash, :now) "
                "RETURNING id"
            ),
            {
                "username": username.strip().lower(),
                "password_hash": password_hash,
                "now": _now(),
            },
        ).scalar_one()


# --------------------------------------------------
# Conversations
# --------------------------------------------------
def create_conversation(admin_id: int, first_message: str, engine=None):
    """Create a conversation titled from its first message; return ID."""
    engine = _get_engine(engine)
    now = _now()

    with engine.begin() as connection:
        return connection.execute(
            text(
                "INSERT INTO conversations "
                "(admin_user_id, title, created_at, updated_at) "
                "VALUES (:admin_id, :title, :now, :now) RETURNING id"
            ),
            {
                "admin_id": admin_id,
                "title": make_title(first_message),
                "now": now,
            },
        ).scalar_one()


def list_conversations(admin_id: int, limit: int = 200, engine=None):
    """Return the admin's conversations, most recently active first."""
    engine = _get_engine(engine)

    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT id, title, created_at, updated_at "
                "FROM conversations WHERE admin_user_id = :admin_id "
                "ORDER BY updated_at DESC, id DESC LIMIT :limit"
            ),
            {"admin_id": admin_id, "limit": limit},
        ).fetchall()

    return [dict(row._mapping) for row in rows]


def get_messages(admin_id: int, conversation_id: int, engine=None):
    """Return all messages of an owned conversation, oldest first.

    Returns None when the conversation does not exist or is not owned by
    the admin.
    """
    engine = _get_engine(engine)

    with engine.connect() as connection:
        owned = connection.execute(
            text(
                "SELECT id FROM conversations "
                "WHERE id = :conversation_id AND admin_user_id = :admin_id"
            ),
            {"conversation_id": conversation_id, "admin_id": admin_id},
        ).first()

        if owned is None:
            return None

        rows = connection.execute(
            text(
                "SELECT role, content, created_at "
                "FROM conversation_messages "
                "WHERE conversation_id = :conversation_id ORDER BY id"
            ),
            {"conversation_id": conversation_id},
        ).fetchall()

    return [dict(row._mapping) for row in rows]


def add_message(
    admin_id: int,
    conversation_id: int,
    role: str,
    content: str,
    engine=None,
):
    """Append a message to an owned conversation and bump its updated_at."""
    if role not in VALID_ROLES:
        raise ValueError("Invalid message role.")

    engine = _get_engine(engine)
    now = _now()

    with engine.begin() as connection:
        touched = connection.execute(
            text(
                "UPDATE conversations SET updated_at = :now "
                "WHERE id = :conversation_id AND admin_user_id = :admin_id"
            ),
            {
                "now": now,
                "conversation_id": conversation_id,
                "admin_id": admin_id,
            },
        ).rowcount

        if touched == 0:
            raise PermissionError("Conversation not found.")

        connection.execute(
            text(
                "INSERT INTO conversation_messages "
                "(conversation_id, role, content, created_at) "
                "VALUES (:conversation_id, :role, :content, :now)"
            ),
            {
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
                "now": now,
            },
        )


def rename_conversation(
    admin_id: int,
    conversation_id: int,
    title: str,
    engine=None,
) -> bool:
    """Rename an owned conversation. Return False if it is not found."""
    cleaned = re.sub(r"\s+", " ", str(title)).strip()

    if not cleaned:
        raise ValueError("Title cannot be empty.")

    cleaned = cleaned[:STORED_TITLE_MAX_LENGTH]
    engine = _get_engine(engine)

    with engine.begin() as connection:
        changed = connection.execute(
            text(
                "UPDATE conversations SET title = :title "
                "WHERE id = :conversation_id AND admin_user_id = :admin_id"
            ),
            {
                "title": cleaned,
                "conversation_id": conversation_id,
                "admin_id": admin_id,
            },
        ).rowcount

    return changed > 0


def delete_conversation(
    admin_id: int,
    conversation_id: int,
    engine=None,
) -> bool:
    """Delete an owned conversation and its messages."""
    engine = _get_engine(engine)

    with engine.begin() as connection:
        owned = connection.execute(
            text(
                "SELECT id FROM conversations "
                "WHERE id = :conversation_id AND admin_user_id = :admin_id"
            ),
            {"conversation_id": conversation_id, "admin_id": admin_id},
        ).first()

        if owned is None:
            return False

        # Explicit delete keeps this correct even where the database
        # does not enforce ON DELETE CASCADE.
        connection.execute(
            text(
                "DELETE FROM conversation_messages "
                "WHERE conversation_id = :conversation_id"
            ),
            {"conversation_id": conversation_id},
        )
        connection.execute(
            text(
                "DELETE FROM conversations "
                "WHERE id = :conversation_id AND admin_user_id = :admin_id"
            ),
            {"conversation_id": conversation_id, "admin_id": admin_id},
        )

    return True
