"""Central lookup for LLM settings (environment first, then Streamlit secrets)."""

import os

from dotenv import load_dotenv

load_dotenv()

PLACEHOLDER_MARKERS = ("your_", "<", "changeme")


def get_setting(name: str) -> str | None:
    """Return a setting from the environment, else from st.secrets."""

    value = os.getenv(name)

    if value and value.strip():
        return value.strip()

    try:
        import streamlit as st

        secret = st.secrets.get(name)
    except Exception:
        # No Streamlit runtime or no secrets file.
        return None

    if secret and str(secret).strip():
        return str(secret).strip()

    return None


def _is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def get_groq_settings() -> tuple[str, str]:
    """Return (api_key, model). Raise RuntimeError with a fix if missing."""

    api_key = get_setting("GROQ_API_KEY")
    model = get_setting("GROQ_MODEL")

    if not api_key or _is_placeholder(api_key):
        raise RuntimeError(
            "GROQ_API_KEY is missing. Set it in .env locally or in "
            "Streamlit Settings > Secrets. Create a key at "
            "https://console.groq.com/keys."
        )

    if not model or _is_placeholder(model):
        raise RuntimeError(
            "GROQ_MODEL is missing. Set it to a model ID enabled for "
            "your Groq account. See https://console.groq.com/docs/models "
            "or the Models list in the Groq console."
        )

    return api_key, model
