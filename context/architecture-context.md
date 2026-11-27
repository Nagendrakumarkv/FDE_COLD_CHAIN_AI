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
   reasoner = Groq (ChatGroq) with bound tools and SYSTEM_PROMPT
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
| LLM settings | `GROQ_API_KEY` and `GROQ_MODEL`, read by `agent/config.py` from the environment, then `st.secrets` | Required |
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

`invoke_model_with_retry` retries up to 3 attempts, only for 429, 5xx, timeout and connection errors (`classify_model_error`). It sleeps for the `Retry-After` header when present, else 2^n seconds, and does not retry when the wait exceeds 20 seconds. 401, 403, 404 and other errors fail at once. `reason()` turns any failure into a safe, specific message (missing config, bad key, model not available, rate limit with wait time, timeout, server error). There is no fallback to another provider. `app.py` catches any remaining exception and shows a generic error.