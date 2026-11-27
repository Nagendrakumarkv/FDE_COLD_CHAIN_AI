Feature Specification: Replace Gemini API with Groq API

1. Objective
Replace the existing Google Gemini LLM integration with Groq Cloud using
a model available to the user's Groq Free tier. This is a provider
migration, not an agent redesign.

Preserve the current Streamlit UI, LangGraph workflow, prompts, tool
definitions, SQL safety, Neon PostgreSQL, Qdrant SOP retrieval,
SentenceTransformer embeddings, weather integration, audit logging, and
conversation behavior.

2. Existing project context
Known architecture: - Streamlit UI and hosting - LangGraph agent
orchestration - Google Gemini (current provider; to be replaced) - Neon
PostgreSQL (previously verified with 6,337 logistics records) - Qdrant
Cloud (previously verified with 4 SOP chunks) - Sentence Transformers:
all-MiniLM-L6-v2 - Weather tool/API - Audit log:
logs/agent_audit.jsonl

Before coding, inspect the repository. Identify the actual Gemini client
initialization, LangGraph nodes, tool binding, structured-output usage,
streaming, retries, configuration loading, tests, and documentation. Do
not assume file names or rewrite modules based only on this
specification.

3. Target provider and configuration
Use Groq Cloud API.

GROQ_API_KEY: Groq API key
GROQ_MODEL: active model ID enabled for the user's account
OpenAI-compatible base URL, only if using the OpenAI client:
https://api.groq.com/openai/v1
Prefer the official langchain-groq integration (ChatGroq) when
the existing app uses LangChain chat-model interfaces and versions
are compatible.
Otherwise use the smallest compatible official Groq client approach.
Do not introduce multiple clients/SDKs unnecessarily.
Do not hard-code an assumed model ID. Read it from GROQ_MODEL and
validate it. Document how to select an active model available to the
user's account.
Free-tier requirement: Free access is subject to model-specific
request/token limits and may change. Do not claim unlimited usage or
guarantee a fixed quota. Handle 429 rate-limit responses clearly.

4. Implementation requirements
4.1 Repository inspection
Search the entire repository for: - ChatGoogleGenerativeAI -
GoogleGenerativeAI - langchain_google_genai -
google.generativeai - GOOGLE_API_KEY - GEMINI_MODEL

Identify every runtime Gemini call path and all references in tests,
docs, .env.example, Streamlit secrets instructions, and deployment
configuration. Identify Gemini-specific options that Groq does not
support.

4.2 Replace the LLM client
Replace Gemini model construction with Groq model construction.
Preserve the interface expected by LangGraph nodes and downstream
code.
Preserve system/user prompts, message history, tool definitions and
schemas, output parsing, and tool-result handling.
Preserve tool calling for existing SQL, weather, and other tools.
Preserve structured/JSON output where currently used. If the chosen
model lacks a required capability, implement a safe compatible
alternative and test it; do not silently remove the capability.
Preserve streaming if currently used by the UI.
Preserve appropriate timeouts and bounded retries. Respect
Retry-After for rate limits when provided. Never retry
indefinitely.
Never log API keys, authorization headers, or secret values.
4.3 Secrets and configuration
Local .env:

GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=your_enabled_groq_model_id
Streamlit Community Cloud Manage app → Settings → Secrets:

GROQ_API_KEY = "your_groq_api_key"
GROQ_MODEL = "your_enabled_groq_model_id"
Add placeholders (not real secrets) to .env.example.
Keep .env excluded from Git.
Use the existing configuration pattern for local development.
Ensure st.secrets values are loaded before the LLM client is
initialized. os.getenv() does not automatically read st.secrets;
use the existing pattern or a small centralized configuration
helper.
Validate missing key/model with clear actionable errors.
After migration, GOOGLE_API_KEY and GEMINI_MODEL must no longer
be required.
4.4 Dependencies
Add langchain-groq if using ChatGroq; otherwise add the official
groq SDK if using it directly.
Remove langchain-google-genai only after confirming there are no
remaining imports.
Remove other Google GenAI packages only if exclusively used by the
retired integration.
Keep unrelated dependencies unchanged. Avoid broad dependency
upgrades.
4.5 Preserve existing features
Do not break: - Streamlit UI and chat history - LangGraph graph
construction/execution - SQL generation and SQL safety validation - Neon
PostgreSQL connectivity/data - Qdrant connectivity, embeddings, and SOP
retrieval - Weather tool behavior - Tool calling and tool-result
handling - Audit logging - User-friendly error handling

Do not change the embedding model or vector database in this feature.

5. Error handling
Handle at least: - Missing GROQ_API_KEY - Missing/invalid
GROQ_MODEL - 401 authentication failure - 403/404 model permission or
availability failure - 429 rate limit - Network timeout/connection
failure - 5xx provider failure

For 429: respect Retry-After when available, use only bounded retries,
and show a useful message if the limit remains exceeded. Never silently
fall back to Gemini.

Do not expose stack traces or secrets in the normal UI. Redact secrets
from server logs.

6. Testing
Add/update tests for: 1. Groq client initialization from GROQ_API_KEY
and GROQ_MODEL. 2. Clear errors for missing key/model. 3. LangGraph
invocation using Groq. 4. Tool binding for existing tools. 5. Tool
result handling and final answer generation. 6. SQL safety remains
active. 7. Qdrant SOP retrieval remains functional. 8. Safe handling of
401, 403/404, 429, timeout, and 5xx. 9. Automated tests mock the
provider and do not require a real API key.

Run the existing test suite and report the exact command and actual
result. Do not claim tests passed unless they were run. Include an
optional real-key smoke test.

7. Local verification
Add GROQ_API_KEY and GROQ_MODEL to local .env.
Run:
python -m streamlit run app.py
Test a general question.
Test: How many records are in the logistics table?
Test: What does the SOP recommend for temperature excursions?
Test: Which shipments have temperatures above 8°C?
Test the weather question.
Verify tool calls, SQL, Neon, Qdrant retrieval, and audit logging.
Confirm there are no Gemini calls in the runtime path.
Never put real API keys in screenshots, source files, commits, or chat
messages.

8. Streamlit deployment
After local tests pass: 1. Add GROQ_API_KEY and GROQ_MODEL to
deployed app secrets. 2. Remove GOOGLE_API_KEY and GEMINI_MODEL from
Streamlit secrets only after confirming no code path still needs them.
3. Commit and push changes to the connected GitHub branch. 4. Wait for
Streamlit Community Cloud to rebuild/restart. 5. Inspect deployment
logs. 6. Repeat the database, SOP, shipment, and weather tests in the
deployed app.

Keep Neon and Qdrant secrets unchanged. This deployment uses Streamlit
Community Cloud directly; do not add credentials to GitHub Actions or
Docker Hub.

9. Acceptance criteria
All runtime Gemini calls are replaced with Groq.
App uses GROQ_API_KEY and GROQ_MODEL.
Selected model is active and eligible for the user's Groq Free
tier.
Existing LangGraph tool calling works.
SQL, Neon, Qdrant, SOP, weather, and audit features still work.
Errors are clear and secrets are redacted.
Automated tests pass and actual results are reported.
Local Streamlit app works.
Streamlit Community Cloud deployment works with Groq secrets.
No obsolete Gemini dependency/config remains unless a documented
non-runtime use requires it.
10. Kiro instructions
Treat this file as the feature requirement and inspect the current
repository before coding.
Follow context/architecture-context.md,
context/code-standards.md, context/ai-workflow-rules.md, and
existing project conventions.
Do not overwrite unrelated feature specifications.
Do not redesign or refactor the entire agent.
Make the smallest production-quality change.
Before finishing, report:
Files created/modified/deleted.
Summary of each change.
Dependency changes.
Environment/secrets changes.
Tests run and actual results.
Local run instructions.
Streamlit deployment instructions.
Known model/tool-calling limitations.
11. Official references
Groq quickstart: https://console.groq.com/docs/quickstart
Groq client libraries: https://console.groq.com/docs/libraries
Groq OpenAI compatibility: https://console.groq.com/docs/openai
Supported models: https://console.groq.com/docs/models
Rate limits: https://console.groq.com/docs/rate-limits
API errors: https://console.groq.com/docs/errors
