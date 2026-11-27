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
| Streamlit chat UI with example questions | `app.py` |
| Admin login (bcrypt, Neon), logout, login throttling | `agent/auth.py`, `app.py` |
| Saved conversations: sidebar history, reopen, rename, delete with confirmation | `tools/chat_store.py`, `app.py` |
| LangGraph agent on Groq with three tools and per-session memory | `agent/orchestrator.py` |
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
- Public sign-up, roles and rate limiting beyond the login lockout. Admin accounts are created only with the script.
- Persistent conversation memory across restarts.
- Real-time IoT streaming or alerting.
- A custom front end beyond Streamlit (`ui/` is empty).

## Data

- `data/logistics.csv`: about 6,337 rows, 26 columns (timestamp, GPS, fuel rate, ETA variation, `iot_temperature`, `cargo_condition_status`, `route_risk_level`, `risk_classification`, `delivery_time_deviation` and others). Loaded into the `logistics` table by `scripts/ingest_data.py`.
- `documents/`: `cold_chain_sop.txt` and `emergency_sop.md`. They cover the 2-8 C range for healthcare cargo, excursion handling, high-risk routes, driver fatigue and severe weather.

## Tech stack

Python 3.12, Streamlit, LangGraph, LangChain, Groq (model set by `GROQ_MODEL`, via `langchain-groq`), SQLAlchemy and psycopg2, PostgreSQL 17 / Neon, ChromaDB, Qdrant, sentence-transformers (`all-MiniLM-L6-v2`), pandas, pypdf, pytest, Docker.

## Live deployment

The app is deployed on Streamlit Community Cloud:

**https://fdecoldchainai-qnmgdjmnsgln9wnxn78y5k.streamlit.app/**

It uses Neon PostgreSQL (`DB_TARGET=neon`) and Qdrant Cloud (`VECTOR_DB_PROVIDER=qdrant`), because Streamlit Cloud has no local PostgreSQL and its disk is not persistent.

### Deploy to Streamlit Community Cloud, step by step

1. **Prepare the cloud services first.**
   - Neon: create a project and copy the connection string (`DATABASE_URL`). Load the data with `python scripts/ingest_data.py` while `DB_TARGET=neon` is set locally.
   - Qdrant Cloud: create a cluster, copy the cluster URL and API key. Load the SOP vectors with `python rag/ingest.py` (or `python rag/migrate_chroma_to_qdrant.py` to copy an existing Chroma store) while `VECTOR_DB_PROVIDER=qdrant` is set.
   - Groq: create an API key at https://console.groq.com/keys and pick a model enabled for your account (https://console.groq.com/docs/models).
2. **Check the repository.**
   - `app.py` is at the repository root (it is the entry point).
   - `requirements.txt` lists every dependency (it already includes `streamlit`, `qdrant-client`, `langchain-groq`).
   - `.env` is listed in `.gitignore`. Never commit it.
3. **Create the first admin once** (after the app has started once, or directly): `python -m scripts.create_admin` with `DB_TARGET=neon`. It prompts for username and password and stores a bcrypt hash. The app creates the three chat tables itself on startup.
3b. **Push the code to GitHub.** Streamlit Cloud deploys from a GitHub repository (public, or private with access granted).
   ```powershell
   git add .
   git commit -m "Prepare Streamlit deployment"
   git push origin main
   ```
4. **Sign in** at https://share.streamlit.io with your GitHub account and authorize access to the repository.
5. **Create the app.** Click **Create app** (or **New app**), choose **Deploy a public app from GitHub**, then set:
   - Repository: your `cold-chain-ai` repository
   - Branch: `main`
   - Main file path: `app.py`
   - App URL: pick a custom subdomain if you want one
6. **Select the Python version.** Open **Advanced settings** and choose Python 3.12 (matches local development).
7. **Add secrets.** In **Advanced settings > Secrets**, paste TOML with your real values:
   ```toml
   GROQ_API_KEY = "your-groq-key"
   GROQ_MODEL = "your-enabled-groq-model-id"
   DB_TARGET = "neon"
   DATABASE_URL = "postgresql://USER:PASSWORD@HOST/DB?sslmode=require"
   VECTOR_DB_PROVIDER = "qdrant"
   QDRANT_URL = "https://your-cluster.cloud.qdrant.io"
   QDRANT_API_KEY = "your-qdrant-key"
   QDRANT_COLLECTION = "cold_chain_sop"
   ```
   Top-level secrets are exposed to the app as environment variables, so the existing `os.getenv(...)` calls work without code changes. Docker Hub tokens and local `DB_*` variables are not needed.
8. **Deploy.** Click **Deploy**. The first build installs `requirements.txt` and can take several minutes (`sentence-transformers` is large). Watch the logs in **Manage app**.
9. **Verify.** Open the app URL and ask an example question that uses all three sources (database, weather, SOP). Confirm answers return without tool errors.
10. **Update later.** Every `git push` to the deployed branch redeploys automatically. Change secrets under **Manage app > Settings > Secrets**. Use **Reboot app** after secret changes.

### Deployment notes

- Free apps go to sleep after a period of inactivity. The first visit afterward shows a wake-up button and a short delay.
- The audit log (`logs/agent_audit.jsonl`) and any local Chroma data are lost on restart. Rely on Qdrant for vectors.
- Never put real keys in the repository or in this file. If a key was ever committed or shared, rotate it.
- Common failures: `ModuleNotFoundError` means a package is missing from `requirements.txt`. A "missing GROQ_API_KEY" or "missing GROQ_MODEL" or database error means a secret is missing or misspelled. Qdrant errors usually mean the collection was never ingested.

## Related documents

- `workflow.md`: flowcharts and sequence diagrams of the full product workflow.
- `developer-workflow.md`: code walkthrough for new developers, with file, function and line for login and each kind of question.
- `architecture-context.md`: structure, boundaries, invariants.
- `ui-context.md`: Streamlit UI conventions.
- `code-standards.md`: coding rules.
- `ai-workflow-rules.md`: how to work on this repo.
- `progress-tracker.md`: status, known issues, next steps.
- `../PROJECT_OVERVIEW.md`: long-form technical overview.
