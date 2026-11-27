"""Unit tests for the Groq provider. No real API key or network needed."""

import os
import uuid

import groq
import httpx
import pytest
from langchain_core.messages import AIMessage

from agent import audit_logger, config, orchestrator

FAKE_KEY = "gsk_unit_test_key_1234567890"
FAKE_MODEL = "unit-test-model"


@pytest.fixture(autouse=True)
def isolate(monkeypatch, tmp_path):
    """Fake settings, temp audit log, no schema DB read, no sleeping."""
    monkeypatch.setenv("GROQ_API_KEY", FAKE_KEY)
    monkeypatch.setenv("GROQ_MODEL", FAKE_MODEL)
    monkeypatch.setattr(
        audit_logger, "AUDIT_LOG_PATH", tmp_path / "audit.jsonl"
    )
    monkeypatch.setattr(orchestrator, "get_schema_text", lambda: "schema")
    monkeypatch.setattr(orchestrator.time, "sleep", lambda s: None)


def make_error(cls, status, headers=None):
    request = httpx.Request(
        "POST", "https://api.groq.com/openai/v1/chat/completions"
    )
    response = httpx.Response(status, request=request, headers=headers)
    return cls("failure", response=response, body=None)


class FakeModel:
    """Returns queued items; raises items that are exceptions."""

    def __init__(self, items):
        self.items = list(items)
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        item = self.items.pop(0)

        if isinstance(item, Exception):
            raise item

        return item


# 1-2. Configuration -------------------------------------------------------

def test_create_model_uses_key_and_model(monkeypatch):
    captured = {}

    class FakeChatGroq:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def bind_tools(self, tools):
            captured["tools"] = tools
            return self

    monkeypatch.setattr(orchestrator, "ChatGroq", FakeChatGroq)

    orchestrator.create_model()

    assert captured["model"] == FAKE_MODEL
    assert captured["api_key"] == FAKE_KEY
    assert captured["temperature"] == 0
    assert captured["max_retries"] == 0
    assert captured["timeout"] == orchestrator.MODEL_TIMEOUT_SECONDS


def test_missing_key_gives_clear_error(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY")
    monkeypatch.setattr(config, "get_setting", lambda name: None)

    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        config.get_groq_settings()


def test_missing_model_gives_clear_error(monkeypatch):
    monkeypatch.delenv("GROQ_MODEL")

    with pytest.raises(RuntimeError, match="GROQ_MODEL"):
        config.get_groq_settings()


def test_placeholder_values_are_rejected(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "your_groq_api_key")

    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        config.get_groq_settings()


def test_get_setting_falls_back_to_streamlit_secrets(monkeypatch):
    import streamlit as st

    monkeypatch.delenv("GROQ_API_KEY")
    monkeypatch.setattr(st, "secrets", {"GROQ_API_KEY": "from-secrets"})

    assert config.get_setting("GROQ_API_KEY") == "from-secrets"


# 4. Tool binding ------------------------------------------------------------

def test_real_chatgroq_binds_existing_tools():
    model = orchestrator.create_model()

    names = {
        tool["function"]["name"] for tool in model.kwargs["tools"]
    }

    assert names == {
        "query_logistics",
        "check_weather",
        "search_compliance_sop",
    }


# 3, 5, 6. Graph, tool results, SQL safety ----------------------------------

def tool_call(name, args, call_id="call_1"):
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": call_id}],
    )


def run_graph(monkeypatch, replies, question="test question"):
    fake = FakeModel(replies)
    monkeypatch.setattr(orchestrator, "create_model", lambda: fake)

    answer = orchestrator.ask_agent(
        question, thread_id=f"test-{uuid.uuid4().hex}"
    )

    return answer, fake


def test_graph_runs_tool_then_answers(monkeypatch):
    seen = []

    def fake_execute(query):
        seen.append(query)
        return [{"count": 6337}]

    monkeypatch.setattr(orchestrator, "execute_sql", fake_execute)

    answer, fake = run_graph(
        monkeypatch,
        [
            tool_call(
                "query_logistics",
                {"sql_query": "SELECT COUNT(*) FROM logistics"},
            ),
            AIMessage(content="There are 6337 records."),
        ],
    )

    assert answer == "There are 6337 records."
    assert fake.calls == 2
    assert seen == ["SELECT COUNT(*) FROM logistics"]


def test_destructive_sql_is_blocked(monkeypatch):
    executed = []
    monkeypatch.setattr(
        orchestrator, "execute_sql", lambda q: executed.append(q)
    )

    answer, _ = run_graph(
        monkeypatch,
        [
            tool_call(
                "query_logistics", {"sql_query": "DROP TABLE logistics"}
            ),
            AIMessage(content="I could not run that query."),
        ],
    )

    assert executed == []
    assert answer == "I could not run that query."


# 7. SOP retrieval -----------------------------------------------------------

def test_sop_tool_returns_untrusted_evidence(monkeypatch):
    class FakeCollection:
        def count(self):
            return 4

        def query(self, **kwargs):
            return {
                "documents": [["Escalate excursions above 8 C."]],
                "metadatas": [[{"source": "cold_chain_sop.txt"}]],
                "distances": [[0.1]],
            }

    class FakeEmbedder:
        def encode(self, texts, normalize_embeddings=True):
            import numpy as np

            return np.zeros((len(texts), 384))

    from rag import retriever

    monkeypatch.setattr(retriever, "get_collection", FakeCollection)
    monkeypatch.setattr(retriever, "model", FakeEmbedder())

    result = orchestrator.search_compliance_sop.invoke(
        {"question": "temperature excursion"}
    )

    evidence = result["untrusted_evidence"]

    assert "BEGIN UNTRUSTED RETRIEVED EVIDENCE" in evidence
    assert "cold_chain_sop.txt" in evidence


# 8. Error handling ---------------------------------------------------------

@pytest.mark.parametrize(
    "error, kind",
    [
        (make_error(groq.AuthenticationError, 401), "auth"),
        (make_error(groq.PermissionDeniedError, 403), "model_access"),
        (make_error(groq.NotFoundError, 404), "model_access"),
        (make_error(groq.RateLimitError, 429), "rate_limit"),
        (make_error(groq.InternalServerError, 500), "server"),
        (make_error(groq.InternalServerError, 503), "server"),
        (
            groq.APITimeoutError(
                request=httpx.Request("POST", "https://api.groq.com")
            ),
            "timeout",
        ),
        (
            groq.APIConnectionError(
                request=httpx.Request("POST", "https://api.groq.com")
            ),
            "connection",
        ),
        (RuntimeError("GROQ_API_KEY is missing"), "config"),
        (ValueError("anything else"), "other"),
    ],
)
def test_error_classification(error, kind):
    assert orchestrator.classify_model_error(error)[0] == kind


@pytest.mark.parametrize(
    "cls, status",
    [
        (groq.AuthenticationError, 401),
        (groq.PermissionDeniedError, 403),
        (groq.NotFoundError, 404),
    ],
)
def test_auth_and_access_errors_are_not_retried(cls, status):
    model = FakeModel([make_error(cls, status)] * 3)

    with pytest.raises(cls):
        orchestrator.invoke_model_with_retry(model, [])

    assert model.calls == 1


def test_rate_limit_respects_retry_after(monkeypatch):
    sleeps = []
    monkeypatch.setattr(orchestrator.time, "sleep", sleeps.append)

    model = FakeModel(
        [
            make_error(
                groq.RateLimitError, 429, {"retry-after": "3"}
            ),
            AIMessage(content="ok"),
        ]
    )

    result = orchestrator.invoke_model_with_retry(model, [])

    assert result.content == "ok"
    assert sleeps == [3.0]


def test_long_retry_after_is_not_waited_out():
    model = FakeModel(
        [
            make_error(
                groq.RateLimitError, 429, {"retry-after": "3600"}
            )
        ]
    )

    with pytest.raises(groq.RateLimitError):
        orchestrator.invoke_model_with_retry(model, [])

    assert model.calls == 1


def test_server_errors_retry_a_bounded_number_of_times():
    model = FakeModel([make_error(groq.InternalServerError, 500)] * 5)

    with pytest.raises(groq.InternalServerError):
        orchestrator.invoke_model_with_retry(model, [], attempts=3)

    assert model.calls == 3


def test_failure_returns_safe_message_without_secrets(monkeypatch):
    error = make_error(groq.AuthenticationError, 401)
    fake = FakeModel([error])
    monkeypatch.setattr(orchestrator, "create_model", lambda: fake)

    answer = orchestrator.ask_agent(
        "hello", thread_id=f"test-{uuid.uuid4().hex}"
    )

    assert "GROQ_API_KEY" in answer
    assert FAKE_KEY not in answer
    assert "Traceback" not in answer


def test_rate_limit_message_mentions_wait_time():
    error = make_error(
        groq.RateLimitError, 429, {"retry-after": "42"}
    )

    assert "43 seconds" in orchestrator.model_error_message(error)


def test_audit_sanitize_redacts_groq_keys():
    assert FAKE_KEY not in audit_logger.sanitize(
        f"failed with key {FAKE_KEY}"
    )


# Optional real-key smoke test ----------------------------------------------

@pytest.mark.integration
@pytest.mark.skipif(
    not (os.getenv("GROQ_API_KEY") and os.getenv("GROQ_MODEL")),
    reason="Needs real GROQ_API_KEY and GROQ_MODEL",
)
def test_groq_smoke(monkeypatch):
    monkeypatch.undo()  # drop fake settings from the autouse fixture

    from dotenv import load_dotenv

    load_dotenv()

    answer = orchestrator.ask_agent(
        "Reply with the single word: ready",
        thread_id=f"smoke-{uuid.uuid4().hex}",
    )

    assert isinstance(answer, str) and answer.strip()
