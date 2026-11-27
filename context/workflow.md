# Product Workflow

Diagrams of how Cold Chain AI works, from data setup to a user's answer. They are written in Mermaid, which renders on GitHub and in the Kiro/VS Code markdown preview.

Source files named in each diagram are the ground truth. If code changes, update the matching diagram.

## 1. System overview

```mermaid
flowchart LR
    U[Admin in browser] --> UI[Streamlit UI<br/>app.py]
    UI --> AU[Login gate<br/>agent/auth.py]
    AU --> CS[Chat store<br/>tools/chat_store.py]
    CS --> AD[(Neon: admin_users,<br/>conversations,<br/>conversation_messages)]
    UI --> AG[LangGraph agent<br/>agent/orchestrator.py]
    AG <--> LLM[Groq]
    AG --> SC[Schema text<br/>tools/schema_tool.py]
    AG --> T1[query_logistics<br/>tools/sql_tool.py]
    AG --> T2[check_weather<br/>tools/weather_tool.py]
    AG --> T3[search_compliance_sop<br/>rag/retriever.py]
    T1 --> DB[(PostgreSQL logistics table<br/>local or Neon)]
    T2 --> WX[Open-Meteo API]
    T3 --> VS[(Vector store<br/>Chroma or Qdrant)]
    AG --> AL[Audit log<br/>logs/agent_audit.jsonl]
```

## 2. Request lifecycle (one question)

```mermaid
sequenceDiagram
    actor User
    participant UI as Streamlit app.py
    participant Store as chat_store (Neon)
    participant Agent as ask_agent()
    participant Sec as security.py
    participant G as LangGraph
    participant LLM as Groq
    participant Tool as Tool (SQL / Weather / SOP)
    participant Log as Audit log

    Note over User,UI: Already signed in (see section 10)
    User->>UI: Types question in chat box
    UI->>Store: Create conversation if new, save user message
    UI->>Agent: ask_agent(question, thread conv-ID, history)
    Agent->>Sec: validate_question()
    Sec-->>Agent: clean question (or error)
    Agent->>Log: user_question
    Agent->>G: invoke (recursion_limit 12)
    loop Until Groq answers without a tool call
        G->>LLM: system prompt + table schema + conversation
        LLM-->>G: tool call or final answer
        opt Tool call requested
            G->>Tool: run_tool(...)
            Tool->>Log: tool_started / tool_completed
            Tool-->>G: result or error dict
        end
    end
    G-->>Agent: last message
    Agent->>Log: agent_response
    Agent-->>UI: answer text
    UI->>Store: Save assistant answer
    UI-->>User: Shows answer, sidebar list refreshes
```

## 3. Agent graph (LangGraph)

```mermaid
flowchart TD
    S([START]) --> R[reasoner<br/>calls Groq with retry]
    R -->|tools_condition: tool call| TN[tools<br/>ToolNode]
    TN --> R
    R -->|no tool call| E([END: final answer])
    R -.->|Groq fails| F[Specific safe message<br/>for the error kind,<br/>no unverified result]
    F --> E
```

Conversation memory is kept per `thread_id` (`conv-<conversation id>`) in `MemorySaver`, in process memory. After a restart, `restore_history()` seeds an empty thread with the last 20 saved messages from Neon, so reopened conversations keep their context. Each reasoning step also appends the live `logistics` column list and notes (`tools/schema_tool.py`) to the system prompt.

## 4. Tool execution and safety checks

```mermaid
flowchart TD
    A[Groq requests a tool] --> B{Which tool?}
    B -->|query_logistics| C[validate_sql_readonly]
    B -->|check_weather| D[validate_text + length 120]
    B -->|search_compliance_sop| E[validate_text]
    C -->|rejected: not SELECT, forbidden keyword,<br/>or names admin_users / conversations /<br/>conversation_messages| X[Return error dict<br/>tool failed]
    C -->|ok| C2[execute_sql on PostgreSQL]
    D -->|ok| D2[get_weather: geocode, then current conditions]
    E -->|ok| E2[search_sop top_k=3]
    E2 --> E3[mark_untrusted_evidence<br/>wrap retrieved text as data]
    C2 --> R[Result back to Groq]
    D2 --> R
    E3 --> R
    X --> R
    R --> L[Audit: tool_completed<br/>success or error, duration]
```

Rules enforced: read-only SQL, admin and chat tables unreadable by the agent, secrets redacted in logs, retrieved SOP text treated as untrusted data, raw exception details not shown to the model.

## 5. Model retry

```mermaid
flowchart TD
    A[model.invoke] --> B{Error?}
    B -->|no| OK[Return response]
    B -->|yes| C{Permanent?<br/>401, 403, 404, config}
    C -->|yes| FAIL[Raise: specific safe message<br/>no fallback provider]
    C -->|no| D{Retryable?<br/>429, 5xx, timeout, connection}
    D -->|no| FAIL
    D -->|yes| E{Attempts left, and wait 20s or less?}
    E -->|no| FAIL
    E -->|yes| W[Audit model_retry<br/>wait Retry-After, else 1s then 2s] --> A
```

## 6. SOP knowledge pipeline (RAG)

```mermaid
flowchart LR
    subgraph Ingest [Offline: python -m rag.ingest]
        D[documents/*.txt, md, pdf, csv] --> LD[document_loader]
        LD --> CH[chunker]
        CH --> EM[Embed: all-MiniLM-L6-v2]
        EM --> UP[Delete old chunks for source, then upsert<br/>with source, category, department]
    end
    UP --> VS[(Chroma vector_db/<br/>or Qdrant Cloud)]
    subgraph Query [At question time]
        Q[SOP question] --> QE[Embed question]
        QE --> QS[Query top 3 chunks]
        QS --> RES[content, source, category, distance]
    end
    VS --> QS
```

`VECTOR_DB_PROVIDER` selects the store. `rag/migrate_chroma_to_qdrant.py` copies an existing Chroma store to Qdrant.

## 7. Data setup

```mermaid
flowchart LR
    CSV[data/logistics.csv<br/>about 6,337 rows] --> ING[scripts/ingest_data.py]
    ING --> SEL{DB_TARGET}
    SEL -->|local| PG[(Local / Docker PostgreSQL)]
    SEL -->|neon| NE[(Neon PostgreSQL)]
    DOCS[documents/] --> RI[rag/ingest.py] --> VSTORE[(Chroma or Qdrant)]
    CA[python -m scripts.create_admin<br/>hidden password prompt] --> HASH[bcrypt hash] --> AUS[(admin_users)]
    START[App start] --> ES[chat_store.ensure_schema<br/>creates the 3 chat tables if missing] --> AUS
```

Both the app and the script write to the same database chosen by `DB_TARGET`.

## 8. Environments and deployment

```mermaid
flowchart TD
    DEV[Local dev<br/>streamlit run app.py<br/>.env file] --> GIT[git push to GitHub]
    GIT --> CI[GitHub Actions<br/>ci-cd.yml, currently commented out]
    DEV -.->|once per database| CA2[python -m scripts.create_admin]
    GIT --> SC[Streamlit Community Cloud<br/>auto redeploy on push]
    SC --> APP[Live app<br/>fdecoldchainai-qnmgdjmnsgln9wnxn78y5k.streamlit.app]
    SEC[Streamlit Secrets<br/>GROQ_API_KEY, GROQ_MODEL, DATABASE_URL,<br/>QDRANT_URL, QDRANT_API_KEY ...] --> APP
    APP --> NEON[(Neon PostgreSQL)]
    APP --> QD[(Qdrant Cloud)]
    APP --> GEM[Groq]
    APP --> OM[Open-Meteo]
    DEV -.-> DK[Docker Compose<br/>app + PostgreSQL]
```

Full deployment steps are in `project-overview.md` under "Live deployment". Nobody can sign in until an admin exists in the target database.

## 9. Configuration map

| Variable | Used by | Effect |
|----------|---------|--------|
| `GROQ_API_KEY`, `GROQ_MODEL` | `agent/config.py`, `agent/orchestrator.py` | Groq access and model ID (environment, then Streamlit secrets) |
| `DB_TARGET` (`local` or `neon`) | `tools/sql_tool.py`, `scripts/ingest_data.py` | Chooses the database |
| `DATABASE_URL` | same | Neon connection string |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | same | Local PostgreSQL |
| `VECTOR_DB_PROVIDER` (`chroma` or `qdrant`) | `rag/vector_store.py` | Chooses the vector store |
| `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION` | `rag/vector_store.py` | Qdrant Cloud |
| `CHROMA_PATH` | `rag/vector_store.py` | Local Chroma folder |
| `AUDIT_LOG_PATH` | `agent/audit_logger.py` | Audit log file location |

Login settings are constants in `agent/auth.py` (5 failures, 5-minute lockout, 8-hour session), not environment variables.

## 10. Login and conversation history

```mermaid
flowchart TD
    A[Open app] --> B[init_database: create tables if missing]
    B --> C{auth_user in session<br/>and under 8 hours old?}
    C -->|no| D[Login form only]
    D --> E[authenticate: lockout check,<br/>fetch admin, bcrypt verify]
    E -->|fail| F[Generic invalid-credentials message]
    E -->|locked| G[Try again in N seconds]
    E -->|ok| H[Store auth_user in session, rerun]
    C -->|yes| I[Chat UI + sidebar]
    H --> I
    I --> J[Sidebar: list conversations, newest activity first]
    J -->|open| K[Load messages, owner-checked]
    J -->|rename / delete dialog| L[Update or delete in Neon, owner-checked]
    I --> M[New question]
    M --> N[Create conversation if new, title from first message]
    N --> O[Save user message]
    O --> P[ask_agent with thread conv-ID,<br/>saved history seeds an empty thread]
    P --> Q[Save assistant answer, rerun to refresh sidebar]
    I --> R[Log out: clear session state]
```

The login gate sits in front of everything: until `auth_user` is set, `app.py` calls `st.stop()` before any agent, conversation or sidebar code runs. Every `chat_store` call filters by the signed-in admin's ID.

## 11. Test and verification flow

```mermaid
flowchart LR
    A[Change code] --> B[pytest -m 'not integration'<br/>unit tests, provider and DB mocked]
    B --> C[Optional: integration tests<br/>need GROQ keys and network]
    B --> D[streamlit run app.py<br/>sign in, one question per tool]
    D --> E[git push]
    E --> F[Streamlit Cloud rebuild, repeat checks]
```
