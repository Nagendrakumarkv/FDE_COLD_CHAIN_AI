import logging
import time

import streamlit as st

from agent import auth
from agent.orchestrator import ask_agent
from tools import chat_store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Cold Chain AI Assistant",
    page_icon="🚚",
    layout="wide",
)


# --------------------------------------------------
# Response formatting
# --------------------------------------------------
def extract_response_text(response):
    """Extract readable text from common LangChain model responses."""

    if isinstance(response, str):
        return response.strip()

    if isinstance(response, dict):
        if response.get("type") == "text":
            return str(response.get("text", "")).strip()

        if "messages" in response:
            messages = response["messages"]
            if messages:
                return extract_response_text(messages[-1])

        if "content" in response:
            return extract_response_text(response["content"])

        if "text" in response:
            return str(response["text"]).strip()

        return str(response)

    if isinstance(response, list):
        text_parts = []

        for item in response:
            if isinstance(item, str):
                text_parts.append(item)

            elif isinstance(item, dict):
                # Display text only; ignore signatures and metadata.
                if item.get("type") == "text" and item.get("text"):
                    text_parts.append(item["text"])

            else:
                content = getattr(item, "content", None)

                if content is not None:
                    extracted = extract_response_text(content)
                    if extracted:
                        text_parts.append(extracted)

        return "\n".join(text_parts).strip()

    # Handle LangChain AIMessage objects.
    content = getattr(response, "content", None)

    if content is not None:
        return extract_response_text(content)

    return str(response).strip()




# --------------------------------------------------
# Database setup (runs once per server process)
# --------------------------------------------------
@st.cache_resource(show_spinner=False)
def init_database():
    """Create the admin and chat tables if they are missing."""
    chat_store.ensure_schema()
    return True


try:
    init_database()
except Exception:
    logger.exception("Database initialisation failed")
    st.error(
        "The database is unavailable, so the application cannot start. "
        "Please try again later."
    )
    st.stop()


# --------------------------------------------------
# Authentication
# --------------------------------------------------
def logout():
    """Clear the login and all conversation state."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def show_login():
    """Render the login form. Nothing else is shown until it succeeds."""
    st.title("🚚 Cold Chain AI")
    st.caption("Admin sign in")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")

    if not submitted:
        return

    try:
        admin = auth.authenticate(username, password)
    except auth.LoginLocked as locked:
        st.error(
            "Too many failed attempts. Try again in "
            f"{locked.retry_after_seconds} seconds."
        )
        return
    except Exception:
        logger.exception("Login check failed")
        st.error("Sign in is unavailable right now. Please try again.")
        return

    if admin is None:
        st.error("Invalid username or password.")
        return

    st.session_state.clear()
    st.session_state.auth_user = {
        "id": admin["id"],
        "username": admin["username"],
        "login_at": time.time(),
    }
    st.rerun()


user = st.session_state.get("auth_user")

if user and time.time() - user["login_at"] > auth.SESSION_MAX_SECONDS:
    logout()
    user = None
    st.warning("Your session expired. Please sign in again.")

if not user:
    show_login()
    st.stop()

admin_id = user["id"]


# --------------------------------------------------
# Conversation state
# --------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None


def open_conversation(conversation_id):
    """Load a saved conversation (owned by this admin) into the chat."""
    saved = chat_store.get_messages(admin_id, conversation_id)

    if saved is None:
        st.session_state.conversation_id = None
        st.session_state.messages = []
        st.warning("That conversation is no longer available.")
        return

    st.session_state.conversation_id = conversation_id
    st.session_state.messages = [
        {"role": item["role"], "content": item["content"]}
        for item in saved
    ]


def start_new_chat():
    st.session_state.conversation_id = None
    st.session_state.messages = []


def save_message(role, content):
    """Persist one message. Return False (and warn) if saving fails."""
    try:
        chat_store.add_message(
            admin_id,
            st.session_state.conversation_id,
            role,
            content,
        )
        return True
    except Exception:
        logger.exception("Could not save message")
        st.warning("This message could not be saved to your history.")
        return False


@st.dialog("Rename conversation")
def rename_dialog(conversation_id, current_title):
    new_title = st.text_input(
        "Title", value=current_title, max_chars=200
    )

    if st.button("Save", type="primary"):
        try:
            renamed = chat_store.rename_conversation(
                admin_id, conversation_id, new_title
            )
        except ValueError:
            st.error("Title cannot be empty.")
            return
        except Exception:
            logger.exception("Rename failed")
            st.error("Could not rename the conversation.")
            return

        if not renamed:
            st.error("That conversation is no longer available.")
            return

        st.rerun()


@st.dialog("Delete conversation")
def delete_dialog(conversation_id, title):
    st.write(
        f"Delete **{title}** and all of its messages? "
        "This cannot be undone."
    )

    confirm_col, cancel_col = st.columns(2)

    if confirm_col.button("Delete", type="primary"):
        try:
            chat_store.delete_conversation(admin_id, conversation_id)
        except Exception:
            logger.exception("Delete failed")
            st.error("Could not delete the conversation.")
            return

        if st.session_state.conversation_id == conversation_id:
            start_new_chat()

        st.rerun()

    if cancel_col.button("Cancel"):
        st.rerun()


# --------------------------------------------------
# Sidebar
# --------------------------------------------------
with st.sidebar:
    st.title("🚚 Cold Chain AI")
    st.caption(f"Signed in as {user['username']}")

    if st.button("Log out", use_container_width=True):
        logout()
        st.rerun()

    st.markdown("---")

    if st.button("➕ New chat", use_container_width=True, type="primary"):
        start_new_chat()
        st.rerun()

    st.subheader("Conversations")

    try:
        conversations = chat_store.list_conversations(admin_id)
    except Exception:
        logger.exception("Could not load conversations")
        conversations = []
        st.warning("Conversation history is unavailable.")

    if not conversations:
        st.caption("No saved conversations yet.")

    for conversation in conversations:
        is_active = (
            conversation["id"] == st.session_state.conversation_id
        )

        title_col, edit_col, delete_col = st.columns([6, 1.3, 1.3])

        if title_col.button(
            conversation["title"],
            key=f"open_{conversation['id']}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
        ):
            open_conversation(conversation["id"])
            st.rerun()

        if edit_col.button(
            "✏️",
            key=f"rename_{conversation['id']}",
            help="Rename",
        ):
            rename_dialog(conversation["id"], conversation["title"])

        if delete_col.button(
            "🗑️",
            key=f"delete_{conversation['id']}",
            help="Delete",
        ):
            delete_dialog(conversation["id"], conversation["title"])

    st.markdown("---")
    st.subheader("Available capabilities")

    st.markdown(
        """
        - 📦 Shipment and logistics queries
        - 🌦️ Weather information
        - 📚 SOP and compliance search
        """
    )

    st.caption("Powered by Groq, LangGraph and Streamlit")


# --------------------------------------------------
# Main interface
# --------------------------------------------------
st.title("Cold Chain Logistics AI Assistant")

st.write(
    "Ask questions about shipments, recorded temperatures, "
    "weather conditions, and company SOPs."
)

st.info(
    "Responses depend on available database records, weather data, "
    "and retrieved SOP documents. Verify critical decisions against "
    "your approved operational procedures."
)

with st.expander("Example questions"):
    st.markdown(
        """
        - How many records are in the logistics table?
        - What is the current weather in Los Angeles?
        - Which shipments have temperatures above 8°C?
        - What does the SOP recommend for temperature excursions?
        """
    )


# --------------------------------------------------
# Display existing conversation
# --------------------------------------------------
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# --------------------------------------------------
# Handle new user question
# --------------------------------------------------
if prompt := st.chat_input(
    "Ask about shipments, weather, or SOPs..."
):
    # Create the conversation on the first message and save the question
    # before calling the agent, so it is kept even if the agent fails.
    earlier_messages = list(st.session_state.messages)

    try:
        if st.session_state.conversation_id is None:
            st.session_state.conversation_id = (
                chat_store.create_conversation(admin_id, prompt)
            )
    except Exception:
        logger.exception("Could not create conversation")
        st.error(
            "Your question could not be saved, so it was not sent. "
            "Please try again."
        )
        st.stop()

    conversation_id = st.session_state.conversation_id

    if not save_message("user", prompt):
        st.stop()

    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt,
        }
    )

    with st.chat_message("user"):
        st.markdown(prompt)

    # Call the existing LangGraph agent.
    with st.chat_message("assistant"):
        try:
            with st.spinner("Analyzing your request..."):
                response = ask_agent(
                    question=prompt,
                    thread_id=f"conv-{conversation_id}",
                    history=earlier_messages,
                )

            answer = extract_response_text(response)

            if answer:
                st.markdown(answer)
                save_message("assistant", answer)
            else:
                answer = (
                    "The agent returned no readable response. "
                    "Check the application logs."
                )
                st.warning(answer)

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                }
            )

        except Exception:
            logger.exception("Agent request failed")

            answer = (
                "Sorry, I couldn't complete your request. "
                "Please check the application terminal logs "
                "for details and try again."
            )

            st.error(answer)

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                }
            )

    # Refresh the sidebar so a new or re-ordered conversation shows.
    st.rerun()
