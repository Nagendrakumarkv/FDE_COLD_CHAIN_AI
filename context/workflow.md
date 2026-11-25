# Product Workflow

Diagrams of how Cold Chain AI works, from data setup to a user's answer. They are written in Mermaid, which renders on GitHub and in the Kiro/VS Code markdown preview.

Source files named in each diagram are the ground truth. If code changes, update the matching diagram.

## 1. System overview

```mermaid
flowchart LR
    U[User in browser] --> UI[Streamlit UI<br/>app.py]
    UI --> AG[LangGraph agent<br/>agent/orchestrator.py]
    AG <--> LLM[Google Gemini]
    AG --> T1[query_logistics<br/>tools/sql_tool.py]
    AG --> T2[check_weather<br/>tools/weather_tool.py]
    AG --> T3[search_compliance_sop<br/>rag/retriever.py]
    T1 --> DB[(PostgreSQL<br/>local or Neon)]
    T2 --> WX[Open-Meteo API]
    T3 --> VS[(Vector store<br/>Chroma or Qdrant)]
    AG --> AL[Audit log<br/>logs/agent_audit.jsonl]
```

## 2. Request lifecycle (one question)

```mermaid
sequenceDiagram
    actor User
    participant UI as Streamlit app.py
    participant Agent as ask_agent()
    participant Sec as security.py
    participant G as LangGraph
    participant LLM as Gemini
    participant Tool as Tool (SQL / Weather / SOP)
    participant Log as Audit log

    User->>UI: Types question in chat box
    UI->>Agent: ask_agent(question, thread_id)
    Agent->>Sec: validate_question()
    Sec-->>Agent: clean question (or error)
    Agent->>Log: user_question
    Agent->>G: invoke (recursion_limit 12)
    loop Until Gemini answers without a tool call
        G->>LLM: system prompt + conversation
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
    UI-->>User: Shows answer, saves to session history
```

## 3. Agent graph (LangGraph)

```mermaid
flowchart TD
    S([START]) --> R[reasoner<br/>calls Gemini with retry]
    R -->|tools_condition: tool call| TN[tools<br/>ToolNode]
    TN --> R
    R -->|no tool call| E([END: final answer])
    R -.->|Gemini fails| F[Fallback message:<br/>no unverified result available]
    F --> E
```

Conversation memory is kept per `thread_id` in `MemorySaver` (in process memory, lost on restart).

## 4. Tool execution and safety checks

```mermaid
flowchart TD
    A[Gemini requests a tool] --> B{Which tool?}
    B -->|query_logistics| C[validate_sql_readonly]
    B -->|check_weather| D[validate_text + length 120]
    B -->|search_compliance_sop| E[validate_text]
    C -->|rejected| X[Return error dict<br/>tool failed]
    C -->|ok| C2[execute_sql on PostgreSQL]
    D -->|ok| D2[get_weather: geocode, then current conditions]
    E -->|ok| E2[search_sop top_k=3]
    E2 --> E3[mark_untrusted_evidence<br/>wrap retrieved text as data]
    C2 --> R[Result back to Gemini]
    D2 --> R
    E3 --> R
    X --> R
    R --> L[Audit: tool_completed<br/>success or error, duration]
```

Rules enforced: read-only SQL, secrets redacted in logs, retrieved SOP text treated as untrusted data, raw exception details not shown to the model.

## 5. Model retry

```mermaid
flowchart TD
    A[model.invoke] --> B{Error?}
    B -->|no| OK[Return response]
    B -->|yes| C{Permanent?<br/>bad key, quota, billing}
    C -->|yes| FAIL[Raise: fallback message]
    C -->|no| D{Transient?<br/>timeout, 429, 502, 503}
    D -->|no| FAIL
    D -->|yes| E{Attempts left? max 3}
    E -->|no| FAIL
    E -->|yes| W[Audit model_retry<br/>wait 1s, then 2s] --> A
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
```

## 8. Environments and deployment

```mermaid
flowchart TD
    DEV[Local dev<br/>streamlit run app.py<br/>.env file] --> GIT[git push to GitHub]
    GIT --> CI[GitHub Actions<br/>ci-cd.yml, currently commented out]
    GIT --> SC[Streamlit Community Cloud<br/>auto redeploy on push]
    SC --> APP[Live app<br/>fdecoldchainai-qnmgdjmnsgln9wnxn78y5k.streamlit.app]
    SEC[Streamlit Secrets<br/>GOOGLE_API_KEY, DATABASE_URL,<br/>QDRANT_URL, QDRANT_API_KEY ...] --> APP
    APP --> NEON[(Neon PostgreSQL)]
    APP --> QD[(Qdrant Cloud)]
    APP --> GEM[Google Gemini]
    APP --> OM[Open-Meteo]
    DEV -.-> DK[Docker Compose<br/>app + PostgreSQL]
```

Full deployment steps are in `project-overview.md` under "Live deployment".

## 9. Configuration map

| Variable | Used by | Effect |
|----------|---------|--------|
| `GOOGLE_API_KEY`, `GEMINI_MODEL` | `agent/orchestrator.py` | Gemini access and model name |
| `DB_TARGET` (`local` or `neon`) | `tools/sql_tool.py`, `scripts/ingest_data.py` | Chooses the database |
| `DATABASE_URL` | same | Neon connection string |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | same | Local PostgreSQL |
| `VECTOR_DB_PROVIDER` (`chroma` or `qdrant`) | `rag/vector_store.py` | Chooses the vector store |
| `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION` | `rag/vector_store.py` | Qdrant Cloud |
| `CHROMA_PATH` | `rag/vector_store.py` | Local Chroma folder |
| `AUDIT_LOG_PATH` | `agent/audit_logger.py` | Audit log file location |
