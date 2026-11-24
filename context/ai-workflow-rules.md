# AI Workflow Rules

## Before starting

1. Read the context files in this order: `project-overview.md`, `architecture-context.md`, `ui-context.md`, `code-standards.md`, `ai-workflow-rules.md`, `progress-tracker.md`.
2. Read the code you will change. Do not edit files you have not read.
3. `AGENTS.md` contains a Next.js rules block that does not apply here. This is a Python project. Follow the "Application Building Context" part only.

## Scoping

- Do one task at a time. Do not add unrequested features, refactors or tests.
- If a request is ambiguous or touches several modules, state assumptions or ask before building.
- Keep changes inside the module boundaries in `architecture-context.md`.
- Prefer the smallest change that satisfies the request.
- If a change would break an invariant in `architecture-context.md` (read-only SQL, untrusted evidence, no secrets in logs), stop and ask.

## Safe actions

Ask the user first for:
- Deleting files or data, dropping or altering tables, reloading the database.
- Re-ingesting or deleting vector collections (Chroma or Qdrant).
- Changing `.env`, Docker or CI settings, or anything that costs money (cloud API calls in bulk).
- Git history changes, force pushes, or committing `logs/` and `.env`.

Never read out, print or commit secrets. Variable names are fine, values are not.

## Typical task recipes

**Add a tool**
1. Put the external call in `tools/` (or `rag/`).
2. Add a `@tool` wrapper in `agent/orchestrator.py` using `validate_text` and `run_tool`.
3. Add it to `TOOLS` and mention it in `SYSTEM_PROMPT`.
4. Add a unit test for validation. Mark any network test `integration`.

**Add or change SOP documents**
1. Put the file in `documents/` (.txt, .md, .pdf or .csv).
2. If a new category is needed, update `get_metadata` in `rag/ingest.py`.
3. Run `python -m rag.ingest` (confirm the target `VECTOR_DB_PROVIDER` first).

**Change the database schema or data**
1. Check the real table columns first.
2. Update `scripts/ingest_data.py` and, if kept in sync, `db/init.sql`.
3. Add schema hints to the agent prompt if column names change.

**Change SQL validation**
- Update `agent/security.py` and `tools/sql_tool.py` together, then update `tests/test_security_unit.py`.

## Verification

- Run `pytest -m "not integration"` after any change to `agent/`, `tools/` or `rag/`.
- Run `python -m streamlit run app.py` and ask one question per tool to check the UI end to end. Tell the user to run it, since it is a long-running process.
- Integration tests need `GOOGLE_API_KEY` and network access. Say clearly when they were not run.
- Check the original request point by point before reporting completion. Say what was not verified.

## Delivery and reporting

- Report briefly: what changed, which files, what was verified, what was not.
- Do not claim success from a clean exit alone.
- After each meaningful change, update `progress-tracker.md`.
- If a change alters architecture, scope or standards, update the matching context file first.
- Keep `PROJECT_OVERVIEW.md` in sync only when the user asks.

## Git

- Prefer small commits with a clear message. Stage files by name.
- Do not commit `.env`, `vector_db/` or audit logs that contain real questions.
- Do not rewrite history or force push without being asked.
