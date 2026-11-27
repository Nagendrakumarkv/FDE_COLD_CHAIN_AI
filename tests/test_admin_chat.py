"""Unit tests for admin login and chat history. No network or real DB."""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from agent import auth
from agent.security import validate_sql_readonly
from tools import chat_store
from tools.sql_tool import validate_sql

PASSWORD = "correct horse battery"


@pytest.fixture(autouse=True)
def clean_throttle():
    auth.reset_throttle()
    yield
    auth.reset_throttle()


@pytest.fixture
def engine():
    """In-memory SQLite with the same tables as production."""
    eng = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    with eng.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON"))
        conn.execute(
            text(
                "CREATE TABLE admin_users (id INTEGER PRIMARY KEY "
                "AUTOINCREMENT, username TEXT UNIQUE NOT NULL, "
                "password_hash TEXT NOT NULL, created_at TEXT)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE conversations (id INTEGER PRIMARY KEY "
                "AUTOINCREMENT, admin_user_id INTEGER NOT NULL "
                "REFERENCES admin_users(id) ON DELETE CASCADE, "
                "title TEXT NOT NULL, created_at TEXT, updated_at TEXT)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE conversation_messages (id INTEGER PRIMARY "
                "KEY AUTOINCREMENT, conversation_id INTEGER NOT NULL "
                "REFERENCES conversations(id) ON DELETE CASCADE, "
                "role TEXT NOT NULL, content TEXT NOT NULL, "
                "created_at TEXT)"
            )
        )

    return eng


@pytest.fixture
def admin(engine):
    admin_id = chat_store.create_admin(
        "Alice", auth.hash_password(PASSWORD), engine=engine
    )
    return admin_id


def lookup_for(engine):
    return lambda username: chat_store.get_admin_by_username(
        username, engine=engine
    )


# Authentication --------------------------------------------------------------

def test_password_is_stored_as_bcrypt_hash(engine, admin):
    stored = chat_store.get_admin_by_username("alice", engine=engine)

    assert stored["password_hash"].startswith("$2")
    assert PASSWORD not in stored["password_hash"]


def test_valid_login(engine, admin):
    result = auth.authenticate(
        "Alice", PASSWORD, lookup=lookup_for(engine)
    )

    assert result == {"id": admin, "username": "alice"}


def test_wrong_password_and_unknown_user_are_rejected(engine, admin):
    lookup = lookup_for(engine)

    assert auth.authenticate("alice", "wrong password!", lookup) is None
    assert auth.authenticate("nobody", PASSWORD, lookup) is None
    assert auth.authenticate("", PASSWORD, lookup) is None
    assert auth.authenticate("alice", "", lookup) is None


def test_over_long_password_is_rejected_not_crashing(engine, admin):
    assert (
        auth.authenticate("alice", "x" * 200, lookup_for(engine)) is None
    )


def test_malformed_stored_hash_fails_closed():
    lookup = lambda u: {"id": 1, "username": u, "password_hash": "oops"}

    assert auth.authenticate("alice", PASSWORD, lookup) is None


def test_lockout_after_repeated_failures(engine, admin):
    lookup = lookup_for(engine)
    now = [1000.0]
    clock = lambda: now[0]

    for _ in range(auth.MAX_FAILED_ATTEMPTS):
        assert auth.authenticate("alice", "bad password!", lookup, clock) is None

    # Even the right password is refused while locked.
    with pytest.raises(auth.LoginLocked) as locked:
        auth.authenticate("alice", PASSWORD, lookup, clock)

    assert 0 < locked.value.retry_after_seconds <= auth.LOCKOUT_SECONDS + 1

    now[0] += auth.LOCKOUT_SECONDS + 1

    assert auth.authenticate("alice", PASSWORD, lookup, clock)["id"] == admin


def test_success_clears_failures(engine, admin):
    lookup = lookup_for(engine)

    for _ in range(auth.MAX_FAILED_ATTEMPTS - 1):
        auth.authenticate("alice", "bad password!", lookup)

    assert auth.authenticate("alice", PASSWORD, lookup)
    assert auth.authenticate("alice", "bad password!", lookup) is None
    # Counter restarted, so the next attempts are not locked.
    assert auth.authenticate("alice", PASSWORD, lookup)


# Conversations ---------------------------------------------------------------

def test_conversation_persists_messages_in_order(engine, admin):
    conv = chat_store.create_conversation(
        admin, "How many records?", engine=engine
    )
    chat_store.add_message(admin, conv, "user", "How many records?", engine=engine)
    chat_store.add_message(admin, conv, "assistant", "6337.", engine=engine)

    messages = chat_store.get_messages(admin, conv, engine=engine)

    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[1]["content"] == "6337."


def test_title_comes_from_first_message_and_is_bounded(engine, admin):
    conv = chat_store.create_conversation(admin, "  " + "word " * 40, engine=engine)
    title = chat_store.list_conversations(admin, engine=engine)[0]["title"]

    assert len(title) <= chat_store.TITLE_MAX_LENGTH
    assert title.endswith("...")
    assert conv


def test_list_is_newest_activity_first(engine, admin):
    first = chat_store.create_conversation(admin, "first", engine=engine)
    second = chat_store.create_conversation(admin, "second", engine=engine)

    ids = [c["id"] for c in chat_store.list_conversations(admin, engine=engine)]
    assert ids == [second, first]

    chat_store.add_message(admin, first, "user", "bump", engine=engine)

    ids = [c["id"] for c in chat_store.list_conversations(admin, engine=engine)]
    assert ids == [first, second]


def test_rename(engine, admin):
    conv = chat_store.create_conversation(admin, "old", engine=engine)

    assert chat_store.rename_conversation(admin, conv, "  New   name ", engine=engine)
    assert chat_store.list_conversations(admin, engine=engine)[0]["title"] == "New name"

    with pytest.raises(ValueError):
        chat_store.rename_conversation(admin, conv, "   ", engine=engine)


def test_delete_removes_conversation_and_messages(engine, admin):
    conv = chat_store.create_conversation(admin, "bye", engine=engine)
    chat_store.add_message(admin, conv, "user", "bye", engine=engine)

    assert chat_store.delete_conversation(admin, conv, engine=engine)
    assert chat_store.list_conversations(admin, engine=engine) == []

    with engine.connect() as conn:
        left = conn.execute(
            text("SELECT COUNT(*) FROM conversation_messages")
        ).scalar_one()

    assert left == 0


def test_other_admin_cannot_read_rename_or_delete(engine, admin):
    other = chat_store.create_admin(
        "bob", auth.hash_password(PASSWORD), engine=engine
    )
    conv = chat_store.create_conversation(admin, "private", engine=engine)
    chat_store.add_message(admin, conv, "user", "secret", engine=engine)

    assert chat_store.get_messages(other, conv, engine=engine) is None
    assert not chat_store.rename_conversation(other, conv, "hacked", engine=engine)
    assert not chat_store.delete_conversation(other, conv, engine=engine)

    with pytest.raises(PermissionError):
        chat_store.add_message(other, conv, "user", "intruder", engine=engine)

    assert chat_store.list_conversations(other, engine=engine) == []
    assert len(chat_store.get_messages(admin, conv, engine=engine)) == 1


def test_invalid_role_is_rejected(engine, admin):
    conv = chat_store.create_conversation(admin, "x", engine=engine)

    with pytest.raises(ValueError):
        chat_store.add_message(admin, conv, "system", "hi", engine=engine)


def test_sql_injection_text_is_stored_literally(engine, admin):
    nasty = "x'); DROP TABLE conversations; --"
    conv = chat_store.create_conversation(admin, nasty, engine=engine)
    chat_store.add_message(admin, conv, "user", nasty, engine=engine)

    assert chat_store.get_messages(admin, conv, engine=engine)[0]["content"] == nasty


# The agent must not read credentials or chat history -------------------------

@pytest.mark.parametrize(
    "query",
    [
        "SELECT * FROM admin_users",
        "select password_hash from ADMIN_USERS",
        "SELECT * FROM conversation_messages",
        "SELECT * FROM public.conversations",
        "SELECT * FROM logistics l JOIN admin_users a ON true",
        "SELECT query_to_xml('select 1', true, false, '')",
    ],
)
def test_agent_sql_cannot_touch_admin_tables(query):
    with pytest.raises(ValueError):
        validate_sql_readonly(query)

    with pytest.raises(ValueError):
        validate_sql(query)


def test_agent_sql_on_logistics_is_still_allowed():
    query = "SELECT COUNT(*) FROM logistics"

    assert validate_sql_readonly(query) == query
    validate_sql(query)


# History restore for the agent ----------------------------------------------

def test_restore_history_seeds_only_empty_threads(monkeypatch):
    from agent import orchestrator

    history = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "system", "content": "ignored"},
    ]

    config = {"configurable": {"thread_id": "restore-test-empty"}}
    seeded = orchestrator.restore_history(config, history)

    assert [m["role"] for m in seeded] == ["user", "assistant"]
    assert orchestrator.restore_history(config, None) == []
