# Feature 03 implementation notes

Status: implemented 2026-11-27. Unit tests pass. A real browser login and the Streamlit Cloud deployment are not yet checked.

## Files

| File | Change |
|------|--------|
| `tools/chat_store.py` | New. Creates the three tables (`ensure_schema`) and holds all admin and chat queries. Every conversation query filters by `admin_user_id`. |
| `agent/auth.py` | New. bcrypt hash and verify, login lockout, session length constant. |
| `scripts/create_admin.py` | New. Creates an admin with a hidden password prompt. |
| `app.py` | Login gate, logout, sidebar history, rename and delete dialogs, message saving. The "Clear conversation" button became "New chat". |
| `agent/orchestrator.py` | `ask_agent(..., history=None)` and `restore_history()`: saved messages seed a thread that has no in-memory state (the checkpointer is lost on restart). Last 20 messages. |
| `agent/security.py`, `tools/sql_tool.py` | Reject SQL that names `admin_users`, `conversations`, `conversation_messages`, or uses `query_to_xml`-style functions. The admin tables share the agent's database, so without this the agent could read password hashes. |
| `requirements.txt` | Added `bcrypt>=4.0,<6`. |
| `tests/test_admin_chat.py` | New. 23 tests on SQLite in memory plus validator checks. |

No existing file was deleted.

## Database

Created by `ensure_schema()` at app start. Safe to run repeatedly (`IF NOT EXISTS`).

- `admin_users(id, username UNIQUE, password_hash, created_at)`
- `conversations(id, admin_user_id -> admin_users ON DELETE CASCADE, title, created_at, updated_at)`, index on `(admin_user_id, updated_at DESC)`
- `conversation_messages(id, conversation_id -> conversations ON DELETE CASCADE, role CHECK user/assistant, content, created_at)`, index on `(conversation_id, id)`

The project had no migration tool, so schema creation lives in code. The `logistics` table is untouched.

## Create an admin

```powershell
python -m scripts.create_admin
```

It asks for a username (3-100 characters) and a password typed twice (12 or more characters, at most 72 bytes because of bcrypt). Usernames are stored in lowercase and matched ignoring case. Run it with `DB_TARGET=neon` to create the admin in Neon. Nothing is read from or written to `.env`, and no default account exists.

## Behaviour notes

- Sidebar order is most recent activity first (a new message moves a conversation to the top).
- Title is the first message, trimmed to 60 characters. Rename accepts up to 200.
- A question that cannot be saved is not sent to the agent. A failed save of the answer shows a warning.
- Agent error text (for example "Sorry, I couldn't complete...") is shown but not saved. Model-service messages returned by the agent are saved like any answer.
- Lockout: 5 failures for a username within 5 minutes blocks that username for the rest of the window. It is kept in process memory.
- Session: stored in Streamlit session state, expires 8 hours after login. Logout clears all session state.

## Verification

- `python -m pytest -m "not integration" -q`: **57 passed, 2 deselected**.
- Against the configured Neon database: tables created twice without error, then a temporary admin was created, logged in, wrong password rejected, a conversation was created, saved, renamed, listed and deleted (messages gone), and the temporary admin was removed. The database still holds one earlier admin account (`admin`, id 4) that was there before this run.
- Streamlit `AppTest` against the real app: unauthenticated visit shows the login form and no chat input, and a wrong login shows "Invalid username or password."

Not verified: a successful browser login, the rename and delete dialogs in a browser, and the Streamlit Cloud deployment.

## Deploy

1. Run `python -m scripts.create_admin` once against Neon.
2. `git push`. No new secrets: the app reuses `DATABASE_URL` and `DB_TARGET`. Streamlit Cloud installs `bcrypt` from `requirements.txt`.
3. Open the app, sign in, ask a question, refresh, and confirm the conversation is still in the sidebar.

## Limits

- The agent's database user can still read and write everything. The validators block the new tables, but a read-only database role (progress-tracker issue 2) is the real boundary.
- Lockout state is lost on restart and not shared between instances.
- The conversation list loads up to 200 conversations.
