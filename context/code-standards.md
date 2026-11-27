# Code Standards

Stack: Python 3.12, Streamlit, LangGraph, SQLAlchemy, Chroma/Qdrant. This is not a Next.js project. Ignore the `nextjs-agent-rules` block in `AGENTS.md`.

## General

- Follow PEP 8. Use 4-space indentation, `snake_case` for functions and variables, `UPPER_CASE` for constants, `PascalCase` for classes.
- Add a short docstring to every public function.
- Keep functions small and single-purpose. Match the style already in the file (wrapped calls, trailing commas, double quotes).
- Do not add new features, refactors or tests that were not requested.
- Standard library imports first, third-party second, local last.
- Use `logging` (`logger = logging.getLogger(__name__)`) in modules. No `print` in app code. Scripts and manual test files may print.

## Configuration and secrets

- Read configuration with `os.getenv` after `load_dotenv()`. Add every new variable to `.env` and document its name in `architecture-context.md`.
- Never hard-code, print, log or return API keys, passwords or connection strings. Never read or echo `.env` values in answers.
- Fail early with a clear `ValueError` or `RuntimeError` when required settings are missing, as `get_database_url()` and `get_groq_settings()` do. LLM settings are read through `agent/config.py` so Streamlit secrets work too.

## Security rules

- All user text goes through `validate_question` or `validate_text` before use.
- All SQL from the model goes through `validate_sql_readonly`, then `execute_sql`. Only `SELECT` and `WITH`. Never build SQL by string-joining untrusted values outside the validators.
- SOP search results must pass through `mark_untrusted_evidence`.
- Tools return dicts: `{"data": ...}`, `{"untrusted_evidence": ...}` or `{"error": "<tool> tool failed."}`. Do not return raw exception text to the model.
- Wrap every new tool in `run_tool(...)` so it is audited.
- Pass values through `sanitize` before writing audit details.
- Do not weaken a validator to make a query pass. Fix the query.

## Agent and tools

- Register new tools with `@tool` in `agent/orchestrator.py` and add them to `TOOLS`. The tool docstring is what the model sees, so keep it precise.
- Put external-system code in `tools/` or `rag/`, not in the orchestrator.
- If the system prompt changes, keep the existing safety rules.
- Keep `temperature=0` for the model unless a requirement says otherwise.

## Database

- Use SQLAlchemy `text()` and `engine.connect()`. Queries run in a read-only transaction.
- `scripts/ingest_data.py` is the only place that writes logistics data. The only other writers are `tools/chat_store.py` (admin, conversation and message tables) and `scripts/create_admin.py`. The agent SQL tool stays read-only.
- Passwords are only handled through `agent/auth.py` (bcrypt). Never log or display a password or hash.
- Column names come from `data/logistics.csv`. Check the real table before writing example queries. `db/init.sql` currently does not match it.

## RAG

- Embedding model `all-MiniLM-L6-v2` gives 384-dimension vectors. Do not change it without recreating the vector collection and re-running `python -m rag.ingest`.
- Chunking: 500 characters, 50 overlap. Chunk IDs must stay deterministic (`make_chunk_id`) so re-ingestion replaces old data.
- Any code that must work on both vector stores should use the Chroma-style methods (`count`, `upsert`, `delete`, `query`) exposed by `get_collection()`.

## Testing

- Unit tests live in `tests/` and must not need network or API keys.
- Tests that call Groq, Neon, Qdrant or Open-Meteo must carry `@pytest.mark.integration`.
- Run unit tests with `pytest -m "not integration"`.
- Root `test_*.py` files are manual scripts. Do not add new ones there. Put new tests in `tests/`.

## Dependencies

- Add new packages to `requirements.txt`. Pin versions for anything newly added when practical.
- Do not commit `.env`, `vector_db/`, or audit logs with real data.

## Docker

- The container must bind to `0.0.0.0` and read `PORT`.
- `.dockerignore` excludes `.env`, `logs/`, `vector_db/`, `tests/` and `.git`. Do not copy secrets into the image.
