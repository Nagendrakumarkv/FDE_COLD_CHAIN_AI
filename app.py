import logging
import uuid

import streamlit as st

from agent.orchestrator import ask_agent

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
    """Extract readable text from common LangChain/Gemini responses."""

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
# Session initialization
# --------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "thread_id" not in st.session_state:
    st.session_state.thread_id = uuid.uuid4().hex


# --------------------------------------------------
# Sidebar
# --------------------------------------------------
with st.sidebar:
    st.title("🚚 Cold Chain AI")
    st.caption("Logistics Intelligence Assistant")

    st.markdown("---")
    st.subheader("Available capabilities")

    st.markdown(
        """
        - 📦 Shipment and logistics queries
        - 🌦️ Weather information
        - 📚 SOP and compliance search
        """
    )

    st.markdown("---")

    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.thread_id = uuid.uuid4().hex
        st.rerun()

    st.caption("Powered by Gemini, LangGraph and Streamlit")


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
    # Display and save the user message.
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
                    thread_id=st.session_state.thread_id,
                )

            answer = extract_response_text(response)

            if answer:
                st.markdown(answer)
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