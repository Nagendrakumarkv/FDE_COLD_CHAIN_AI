# Project Overview

## Product definition

**Cold Chain AI Assistant** is a chat application for cold chain logistics operations. A user asks questions in plain language. An AI agent answers using three evidence sources:

1. Shipment records in PostgreSQL (temperatures, route risk, cargo condition, delivery deviation).
2. Current weather from Open-Meteo.
3. Company SOP and compliance documents, searched semantically (RAG).

The project is also a learning and portfolio build from a 24-lesson forward-deployed-engineer (FDE) syllabus kept in `future-reference.txt`.

## Goals

- Give accurate, evidence-based answers about cold chain shipments and compliance.
- Never present invented data. If a tool fails, say which evidence is missing.
- Never declare cargo safe on incomplete evidence.
- Keep database access read-only and keep secrets out of responses and logs.
- Run the same way locally, in Docker, and on a cloud host (Render), with a local or cloud database (Neon) and vector store (Qdrant).

## Features (implemented)

| Feature | Where |
|---------|-------|
| Streamlit chat UI with session history, example questions, clear-conversation button | `app.py` |
| LangGraph agent on Gemini with three tools and per-session memory | `agent/orchestrator.py` |
| Read-only SQL tool (local PostgreSQL or Neon) | `tools/sql_tool.py` |
| Weather tool (geocoding plus current conditions) | `tools/weather_tool.py` |
| SOP search tool (ingest, chunk, embed, retrieve) | `rag/` |
| Switchable vector store: Chroma (default) or Qdrant Cloud, plus a migration script | `rag/vector_store.py`, `rag/migrate_chroma_to_qdrant.py` |
| Input, SQL and untrusted-evidence validation | `agent/security.py` |
| JSONL audit log with secret redaction | `agent/audit_logger.py` |
| Model retry with backoff for transient errors | `agent/orchestrator.py` |
| Docker image, Docker Compose (app + PostgreSQL) | `Dockerfile`, `docker-compose.yml` |
| Unit and integration tests | `tests/` |

## Users

Operations staff and logistics analysts who need quick answers about shipment conditions, weather risk and SOP requirements.

## Scope

In scope:
- Question answering over the three sources above.
- Multi-turn conversation within one browser session.

Out of scope for now:
- Writing to the database or any external system.
- User accounts, authentication and rate limiting.
- Persistent conversation memory across restarts.
- Real-time IoT streaming or alerting.
- A custom front end beyond Streamlit (`ui/` is empty).

## Data

- `data/logistics.csv`: about 6,337 rows, 26 columns (timestamp, GPS, fuel rate, ETA variation, `iot_temperature`, `cargo_condition_status`, `route_risk_level`, `risk_classification`, `delivery_time_deviation` and others). Loaded into the `logistics` table by `scripts/ingest_data.py`.
- `documents/`: `cold_chain_sop.txt` and `emergency_sop.md`. They cover the 2-8 C range for healthcare cargo, excursion handling, high-risk routes, driver fatigue and severe weather.

## Tech stack

Python 3.12, Streamlit, LangGraph, LangChain, Google Gemini (`gemini-2.5-flash` by default), SQLAlchemy and psycopg2, PostgreSQL 17 / Neon, ChromaDB, Qdrant, sentence-transformers (`all-MiniLM-L6-v2`), pandas, pypdf, pytest, Docker.

## Related documents

- `architecture-context.md`: structure, boundaries, invariants.
- `ui-context.md`: Streamlit UI conventions.
- `code-standards.md`: coding rules.
- `ai-workflow-rules.md`: how to work on this repo.
- `progress-tracker.md`: status, known issues, next steps.
- `../PROJECT_OVERVIEW.md`: long-form technical overview.
