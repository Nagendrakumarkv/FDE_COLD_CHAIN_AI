# UI Context

The UI is a single-page **Streamlit** app in `app.py`. There is no custom front end, no canvas and no JavaScript. `ui/` is an empty folder.

## Theme

- Configured in `.streamlit/config.toml`. The only setting there is `fileWatcherType = "none"`. Colors, fonts and base theme use Streamlit defaults.
- Do not add custom CSS unless the user asks for it. If a theme is needed, set it in `.streamlit/config.toml` under `[theme]`.

## Page layout

- `st.set_page_config(page_title="Cold Chain AI Assistant", page_icon="🚚", layout="wide")`.
- **Sidebar:** title "🚚 Cold Chain AI", caption, list of capabilities (shipment queries, weather, SOP search), a "Clear conversation" button, and a footer caption.
- **Main area, top to bottom:**
  1. Title "Cold Chain Logistics AI Assistant" and a one-line description.
  2. `st.info` disclaimer: answers depend on available data, verify critical decisions against approved procedures.
  3. "Example questions" expander.
  4. Chat history rendered with `st.chat_message`.
  5. `st.chat_input` at the bottom.

## Session state

| Key | Meaning |
|-----|---------|
| `st.session_state.messages` | List of `{"role": "user" or "assistant", "content": str}` |
| `st.session_state.thread_id` | `uuid4().hex`, passed to `ask_agent` as the memory key |

"Clear conversation" empties `messages`, creates a new `thread_id`, then calls `st.rerun()`. The new thread ID is what resets agent memory.

## Interaction rules

- Show the user message first, then call `ask_agent(question=..., thread_id=...)` inside `st.chat_message("assistant")` with `st.spinner("Analyzing your request...")`.
- Pass the raw return value through `extract_response_text()`. It handles str, dict, list of content blocks, and LangChain message objects. Show only text blocks and ignore signatures and metadata.
- Empty answer: `st.warning` with a message to check logs.
- Exception: log with `logger.exception`, show a generic `st.error`, never show stack traces, SQL errors or secrets to the user.
- Always append the assistant message (including error text) to `session_state.messages` so history stays consistent.

## Component conventions

- Use Streamlit built-ins (`st.chat_message`, `st.chat_input`, `st.sidebar`, `st.expander`, `st.info`, `st.warning`, `st.error`, `st.spinner`).
- Keep UI code in `app.py`. Do not put database, weather or retrieval calls in it. It talks only to `agent.orchestrator.ask_agent`.
- Use emoji sparingly, as in the existing sidebar and button labels.
- Keep user-facing text short and plain. Include the verify-against-SOP disclaimer wherever answers support operational decisions.
- Use `use_container_width=True` for sidebar buttons.

## Possible future UI work (not started)

- Show cited SOP sources and tool usage in the response.
- Show a table or chart for SQL results.
- Add authentication and rate limiting.
- Screenshots belong in `context/screenshots/`.
