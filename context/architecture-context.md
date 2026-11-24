# Architecture Context

## System structure

```
Streamlit UI (app.py)
   | question + thread_id
   v
agent.orchestrator.ask_agent()
   | validate_question, set_audit_session
   v
LangGraph StateGraph(MessagesState) + MemorySaver, recursion_limit=12
   START -> reasoner -> (tools_condition) -> tools -> reasoner ... -> END
   reasoner = Gemini with bound tools and SYSTEM_PROMPT
   tools    = query_logistics | check_weather | search_compliance_sop
                |                   |                  |
           tools/sql_tool     tools/weather_tool   rag/retriever
                |                   |                  |
         PostgreSQL/Neon       Open-Meteo        Chroma or Qdrant
```

Every tool call is wrapped by `run_tool()` in `agent/orchestrator.py`, which writes audit events and hides raw exceptions from the model.

## Module boundaries

| Module | Owns | Must not |
|--------|------|----------|
| `app.py` | UI, session state, response text extraction | Contain agent, SQL or retrieval logic |
| `agent/orchestrator.py` | Graph, system prompt, tool wrappers, retry, `ask_agent` | Run SQL or HTTP calls directly |
| `agent/security.py` | Input, SQL and evidence validation | Perform I/O |
| `agent/audit_logger.py` | Audit file writes, redaction | Raise errors into the agent flow |
| `tools/` | One external system each (database, weather API) | Import from `agent/` |
| `rag/` | Load, chunk, embed, store, retrieve SOPs | Import from `agent/` |
| `scripts/` | One-off data loading | Be imported by the app |

Dependency direction: `app` -> `agent` -> `tools` and `rag`. Lower layers never import upward.

## Storage model

| Store | Content | Config |
|-------|---------|--------|
| PostgreSQL (local Docker) or Neon | `logistics` table, created from the CSV headers by `df.to_sql` | `DB_TARGET=local` uses `DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD`. `DB_TARGET=neon` uses `DATABASE_URL`. |
| Chroma (default) | Collection `cold_chain_sop`, cosine space | `VECTOR_DB_PROVIDER=chroma`, `CHROMA_PATH` (default `vector_db`) |
| Qdrant Cloud | Collection from `QDRANT_COLLECTION` (default `cold_chain_sop`), 384 dimensions, cosine | `VECTOR_DB_PROVIDER=qdrant`, `QDRANT_URL`, `QDRANT_API_KEY` |
| `logs/agent_audit.jsonl` | One JSON event per line | `AUDIT_LOG_PATH` |
| `MemorySaver` | Conversation state per `thread_id` | In process only, lost on restart |

Vector record shape: Chroma stores document, embedding and metadata. The Qdrant adapter (`QdrantCollection`) mimics the Chroma API and stores payload `{original_id, document, metadata}` with a uuid5 point ID. Metadata keys: `source`, `file_type`, `category`, `department`, `chunk_index`.

## RAG pipeline

`documents/` -> `document_loader.load_document` (.txt, .md, .pdf, .csv) -> `chunker.create_chunks` (500 chars, 50 overlap) -> SentenceTransformer `all-MiniLM-L6-v2` (384 dimensions, normalised) -> `vector_store.get_collection()`.

`rag/ingest.py` deletes a file's old chunks (`where={"source": filename}`) before upserting. Chunk IDs come from `make_chunk_id`. `retriever.search_sop(question, top_k=3)` returns content, source, category, department and distance.

## Invariants

1. **Read-only SQL.** Queries must be one `SELECT` or `WITH` statement. They run inside `SET TRANSACTION READ ONLY`. Both `validate_sql_readonly` (agent layer) and `validate_sql` (tool layer) apply.
2. **Retrieved text is untrusted.** SOP results always pass through `mark_untrusted_evidence` before reaching the model.
3. **No raw errors to the model.** `run_tool` returns `{"error": "<tool> tool failed."}`. Details go to the server log only.
4. **No secrets in logs or responses.** All audit values pass through `sanitize`. Environment values are never printed.
5. **Audit never breaks the agent.** `record_audit` swallows write errors.
6. **Bounded work.** Question and tool input max 2000 chars, location max 120, retrieved evidence max 8000, graph `recursion_limit` 12, model retries max 3.
7. **Embedding dimension is 384.** Changing the embedding model requires a new Qdrant collection and re-ingestion.
8. **One vector provider at a time**, selected by `VECTOR_DB_PROVIDER`. The migration script requires `qdrant`.
9. **Honest answers.** The system prompt requires disclosing missing evidence, citing SOP filenames and never declaring cargo safe on incomplete data.

## Error handling and retries

`invoke_model_with_retry` retries up to 3 times with 2^n second backoff, only for errors that look transient (timeout, connection, 429, 502, 503). Quota, billing and auth errors fail at once. If the model call fails, `reason()` returns a fixed apology message. `app.py` catches any remaining exception and shows a generic error.

## Deployment

- **Docker image:** `python:3.12-slim`, runs `streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT:-10000}`.
- **Compose:** `postgres` (postgres:17, db `cold_chain`, healthcheck, named volume) and `app` (mounts `./vector_db` and `./logs`). The compose file maps `8501:8501`, so `PORT=8501` must be set for the app service.
- **Cloud:** Render for the app, Neon for PostgreSQL, Qdrant Cloud for vectors.
- **CI/CD:** `.github/workflows/ci-cd.yml` is fully commented out. The planned flow is pytest, then Docker Hub build and push on pushes to main.

## Known structural issues

See `progress-tracker.md` for the live list. Main items: `db/init.sql` does not match the CSV schema, the two SQL validators are duplicated, there is no database-level read-only role, and Qdrant index creation runs on every query.
