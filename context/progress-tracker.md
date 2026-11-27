# Progress Tracker

Last updated: 2026-11-24

## Current phase

Working prototype with deployment support. The agent, three tools, RAG, security checks, audit log and Streamlit UI run end to end. Work now is hardening (schema, read-only DB role, CI, tests).

## Completed

- [x] PostgreSQL logistics table loaded from `data/logistics.csv` (`scripts/ingest_data.py`).
- [x] Read-only SQL tool with validation and `SET TRANSACTION READ ONLY` (`tools/sql_tool.py`, `agent/security.py`).
- [x] Weather tool using Open-Meteo geocoding and current conditions (`tools/weather_tool.py`).
- [x] RAG pipeline: loader, chunker, ingestion, retriever (`rag/`).
- [x] SOP documents ingested: `cold_chain_sop.txt`, `emergency_sop.md`.
- [x] LangGraph agent with memory, bounded retries and safe error messages (`agent/orchestrator.py`).
- [x] Prompt-injection safeguards: untrusted-evidence wrapping, system prompt rules.
- [x] Audit logging with redaction to `logs/agent_audit.jsonl`.
- [x] Streamlit chat UI (`app.py`).
- [x] Docker image and Docker Compose with PostgreSQL.
- [x] Neon support via `DB_TARGET=neon`.
- [x] Qdrant Cloud support, provider switch and Chroma-to-Qdrant migration script.
- [x] Render deployment settings (`PORT`-based Streamlit command).
- [x] Unit tests for security (`tests/test_security_unit.py`) and one integration test.
- [x] Context documentation and `PROJECT_OVERVIEW.md`.
- [x] Deployed to Streamlit Community Cloud (https://fdecoldchainai-qnmgdjmnsgln9wnxn78y5k.streamlit.app/); steps documented in `project-overview.md`.

- [x] Feature 01, schema-aware SQL: live table schema plus column notes added to the agent prompt (`tools/schema_tool.py`). Spec: `feature-specs/01-schema-aware-sql/feature.md`. Not yet tested with live model questions.

- [x] Feature 02, Groq migration: `ChatGroq` replaces Gemini, `agent/config.py` reads `GROQ_API_KEY`/`GROQ_MODEL` from env or Streamlit secrets, error classification with `Retry-After` handling, `.env.example` added, 34 unit tests pass (mocked provider). Spec: `feature-specs/02-groq-api-migration/feature.md`.

## In progress / pending

- [ ] Feature 02 manual steps: add `GROQ_API_KEY` and `GROQ_MODEL` to local `.env`, run the local checks, add both to Streamlit secrets, push, verify the deployed app, then remove `GOOGLE_API_KEY` and `GEMINI_MODEL` from `.env` and Streamlit secrets and rotate the old Gemini key.

- [ ] CI/CD: `.github/workflows/ci-cd.yml` is fully commented out. Re-enable the test job, then the Docker Hub push.
- [ ] Course syllabus items in `future-reference.txt` that are not yet implemented (check the list there).

## Known issues (by priority)

1. **Schema mismatch (partly fixed by feature 01).** The agent prompt now includes the real schema. `db/init.sql` still differs from the CSV-derived table and nothing uses it. Align or remove it (needs approval).
2. **No database-level read-only role.** Compose uses `admin` with a default password `admin123`. Create a read-only role for the agent.
3. **Audit log tracked in git.** `logs/agent_audit.jsonl` holds question and answer text. Add it to `.gitignore` and untrack it (needs user approval).
4. **Port mismatch in compose.** Container listens on `PORT` (default 10000), compose maps `8501:8501`. Set `PORT=8501` for the app service or change the mapping.
5. **Duplicated SQL validators** with different rules. Keyword matching blocks harmless identifiers (`copy`, `call`) and any `;`, even inside string literals.
6. **Qdrant overhead.** `get_qdrant_collection()` checks the collection and creates three payload indexes on every query, and `count()` is called twice per search.
7. **Fragile Qdrant `$and` filter** (`convert_filter` uses only `.must[0]` of each condition).
8. **Stale references.** `SYSTEM_PROMPT` says "ChromaDB RAG". `CHROMA_HOST` and `CHROMA_PORT` in `.env` are unused. `future-reference.txt` mentions a chroma compose service that does not exist.
9. **Startup cost.** Embedding model loads at import time and is not cached in the image. The Groq model object is rebuilt on every reasoning step.
10. **No auth or rate limiting.** `MemorySaver` is in-memory only. `recursion_limit=12` may cut long tool chains.
11. **Unpinned dependencies** in `requirements.txt`.
12. **Test coverage is thin.** One integration test (weather only). SQL and SOP integration cases are commented out. Root `test_*.py` files are manual scripts and `test_security.py` duplicates the unit tests.
13. **Empty `ui/` folder** and `context/feature-specs`, `context/screenshots` folders.

## Next steps (suggested order)

1. ~~Put the real table schema in the agent prompt~~ (done, feature 01). Fix or remove `db/init.sql`.
2. Create a read-only database user and use it for the agent.
3. Untrack the audit log and add it to `.gitignore`.
4. Fix the compose port mapping.
5. Merge the two SQL validators into one module and add tests for edge cases.
6. Cache the Qdrant collection check and payload indexes.
7. Re-enable CI with `pytest -m "not integration"`.
8. Pin dependencies.
9. Show SOP sources and tool usage in the UI.

## Open questions

- Which database target is the default for deployment (Neon or Docker PostgreSQL)?
- Which vector store is used in production (Qdrant Cloud or local Chroma)?
- Is authentication needed before sharing the Render deployment?
- Should the agent have a retention policy for audit logs?

## Change log

| Date | Change |
|------|--------|
| 2026-11-24 | Filled all context files from the current codebase. Added `PROJECT_OVERVIEW.md`. |
| 2026-11-25 | Added Streamlit deployment steps and `workflow.md`. Implemented feature 01 (schema-aware SQL). |
| 2026-11-25 | Implemented feature 02 (Groq migration). Live key checks and deployment pending. |
