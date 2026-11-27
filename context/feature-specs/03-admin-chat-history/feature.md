# Feature: Admin Login & Conversation Management

**ID:** `03-admin-chat-history`

## Goal
Allow only authenticated admins to access Cold Chain AI. Authenticate login credentials against Neon PostgreSQL. Persist conversations and messages, with sidebar history, rename and delete functionality.

## Requirements

1. Create a login page with username and password input fields.
2. Accept the admin's normal plain-text password through the login form.
3. Validate the entered username against `admin_users` in Neon PostgreSQL.
4. Retrieve the stored password hash and verify the entered password using bcrypt.
5. Never store or compare passwords as plain text in the database.
6. No public registration. Admin accounts are created separately in the database.
7. Maintain authentication using Streamlit session state and provide logout.
8. Block all application and agent functionality until authentication succeeds.
9. Persist every user message and AI response in Neon PostgreSQL.
10. Display all saved conversations in the left sidebar, newest first.
11. Selecting a conversation must load its complete message history.
12. Provide an option to edit the conversation title and immediately update PostgreSQL.
13. Provide a delete option with confirmation. Delete the conversation and its messages from PostgreSQL.
14. Create a new conversation when the admin starts a new chat. Generate an initial title from the first user message.
15. Preserve the existing LLM provider, LangGraph tools, SQL safety, Neon logistics data, Qdrant retrieval, weather integration and audit logging.

## Database

Inspect the existing schema and migration approach before making changes.

Required tables:

- `admin_users`: id, username, password_hash, created_at
- `conversations`: id, admin_user_id, title, created_at, updated_at
- `conversation_messages`: id, conversation_id, role, content, created_at

Add appropriate foreign keys and indexes. Deleting a conversation must also delete its messages.

## Authentication Flow

1. Admin opens the application.
2. Display the login page.
3. Admin enters username and plain-text password.
4. Fetch the matching admin record from PostgreSQL.
5. Verify the entered password against the stored bcrypt hash.
6. If valid, create an authenticated Streamlit session.
7. Redirect/display the Cold Chain AI chat interface.
8. If invalid, display a generic invalid-credentials message.
9. Logout must clear authentication and selected-conversation state.

## Security

- Store only bcrypt password hashes in `admin_users`.
- Never store plain-text passwords.
- Use parameterized SQL/ORM queries.
- Never hard-code admin credentials.
- Create admin accounts separately using securely generated password hashes.
- Protect all agent operations and conversation actions.
- Verify conversation ownership before reading, renaming or deleting.
- Prevent unauthorized access to other admin accounts' conversations.
- Never expose password hashes or secrets in UI or logs.
- Use secure session handling and appropriate login-attempt protection.

## Acceptance Criteria

- [ ] Login page appears when unauthenticated.
- [ ] Admin can enter username and password.
- [ ] Valid credentials allow login.
- [ ] Invalid credentials are rejected.
- [ ] Passwords are verified using bcrypt.
- [ ] No unauthenticated access to agent functionality.
- [ ] Logout blocks access until the next successful login.
- [ ] Conversations and messages persist after refresh/restart.
- [ ] Sidebar displays saved conversations.
- [ ] Selecting a conversation restores its messages.
- [ ] Rename updates PostgreSQL and the sidebar.
- [ ] Delete removes the conversation and associated messages.
- [ ] Existing AI agent functionality continues working.

## Kiro Instructions

Inspect the existing application, database layer, schema, authentication and Streamlit session handling before coding.

Follow:
- `context/architecture-context.md`
- `context/code-standards.md`
- `context/ai-workflow-rules.md`

Implement the smallest production-ready change. Do not rewrite unrelated modules.

After implementation, report:
1. Files created, modified and deleted.
2. Database schema/migration changes.
3. Admin account creation instructions.
4. Dependencies and configuration changes.
5. Tests executed and actual results.
6. Local and Streamlit deployment instructions.