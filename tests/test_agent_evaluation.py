import uuid

import pytest

from agent.orchestrator import ask_agent


@pytest.mark.integration
@pytest.mark.parametrize(
    "question",
    [
        # "How many records are in the logistics table?",
        "What is the current weather in Los Angeles?",
        # "What does the SOP recommend for temperature excursions?",
    ],
)
def test_agent_returns_response(question):
    thread_id = f"test-{uuid.uuid4().hex}"

    response = ask_agent(
        question=question,
        thread_id=thread_id,
    )

    assert isinstance(response, str)
    assert response.strip()