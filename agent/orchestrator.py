import logging
import os
import time

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from agent.audit_logger import (
    audit_event,
    reset_audit_session,
    sanitize,
    set_audit_session,
    summarize_result,
)
from tools.sql_tool import execute_sql
from tools.weather_tool import get_weather
from rag.retriever import search_sop

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are a Cold Chain Logistics AI Assistant.

Tools:
- PostgreSQL: logistics records and shipment temperatures.
- Weather API: current weather.
- ChromaDB RAG: company SOPs and compliance documents.

Rules:
- Use actual tool results only.
- Never invent SQL, weather, or SOP results.
- If a tool fails, disclose the limitation.
- Use another tool if useful and available.
- Cite SOP source filenames when available.
- Never declare cargo safe using incomplete evidence.
- Keep answers concise and factual.
"""


def record_audit(event_type, status="info", **details):
    """Prevent audit-file errors from crashing agent execution."""
    try:
        audit_event(event_type, status=status, **details)
    except Exception:
        logger.exception("Failed to write audit event: %s", event_type)


def is_transient_error(error: Exception) -> bool:
    """Identify errors that may succeed on a later attempt."""
    status_code = getattr(error, "status_code", None)

    if status_code in (500, 502, 503, 504):
        return True

    name = type(error).__name__.lower()
    message = str(error).lower()

    permanent_indicators = (
        "insufficient_quota",
        "credit_balance_exhausted",
        "invalid api key",
        "unauthorized",
        "permission denied",
    )

    if any(item in message for item in permanent_indicators):
        return False

    transient_names = (
        "timeout",
        "connection",
        "temporarilyunavailable",
    )

    transient_messages = (
        "timed out",
        "connection reset",
        "service unavailable",
        "internal server error",
        "bad gateway",
    )

    return (
        any(item in name for item in transient_names)
        or any(item in message for item in transient_messages)
    )


def run_tool(tool_name, operation, **inputs):
    """Audit a tool's execution and return its result."""
    start = time.perf_counter()

    record_audit(
        "tool_call_started",
        status="started",
        tool_name=tool_name,
        **inputs,
    )

    try:
        result = operation()
        duration_ms = round(
            (time.perf_counter() - start) * 1000, 2
        )

        failed = isinstance(result, dict) and "error" in result

        record_audit(
            "tool_call_finished",
            status="error" if failed else "success",
            tool_name=tool_name,
            duration_ms=duration_ms,
            result=summarize_result(result),
        )

        return result

    except Exception as error:
        duration_ms = round(
            (time.perf_counter() - start) * 1000, 2
        )

        record_audit(
            "tool_call_finished",
            status="error",
            tool_name=tool_name,
            duration_ms=duration_ms,
            error_type=type(error).__name__,
            error=sanitize(error),
        )

        logger.exception("%s failed", tool_name)

        return {
            "error": (
                f"{tool_name} failed. "
                "No verified result is available."
            )
        }


@tool
def query_logistics(sql_query: str) -> dict:
    """Query logistics records using validated read-only SQL."""
    return run_tool(
        "postgresql",
        lambda: {"data": execute_sql(sql_query)},
        sql_query=sanitize(sql_query),
    )


@tool
def check_weather(location: str) -> dict:
    """Retrieve current weather for a named location."""
    return run_tool(
        "weather",
        lambda: {"data": get_weather(location)},
        location=location,
    )


@tool
def search_compliance_sop(question: str) -> dict:
    """Search company SOP and compliance documents."""
    return run_tool(
        "sop_search",
        lambda: {"data": search_sop(question, top_k=3)},
        search_question=question,
    )


TOOLS = [
    query_logistics,
    check_weather,
    search_compliance_sop,
]


def create_model():
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY is missing from .env."
        )

    return ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        google_api_key=api_key,
        temperature=0,
        max_retries=0,
    ).bind_tools(TOOLS)


model_with_tools = create_model()


def invoke_model_with_retry(messages):
    """Retry transient Gemini failures at most three times."""
    for attempt in range(1, 4):
        try:
            return model_with_tools.invoke(messages)

        except Exception as error:
            if attempt == 3 or not is_transient_error(error):
                raise

            delay = 2 ** (attempt - 1)

            record_audit(
                "gemini_retry",
                status="retrying",
                attempt=attempt,
                delay_seconds=delay,
                error_type=type(error).__name__,
            )

            time.sleep(delay)


def reason(state: MessagesState):
    """Run Gemini reasoning and audit its outcome."""
    start = time.perf_counter()

    try:
        response = invoke_model_with_retry(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                *state["messages"],
            ]
        )

        record_audit(
            "gemini_reasoning",
            status="success",
            duration_ms=round(
                (time.perf_counter() - start) * 1000, 2
            ),
            requested_tool_count=len(
                getattr(response, "tool_calls", [])
            ),
        )

        return {"messages": [response]}

    except Exception as error:
        record_audit(
            "gemini_reasoning",
            status="error",
            duration_ms=round(
                (time.perf_counter() - start) * 1000, 2
            ),
            error_type=type(error).__name__,
            error=sanitize(error),
        )

        logger.exception("Gemini reasoning failed")

        if "429" in str(error) or "quota" in str(error).lower():
            message = (
                "Gemini API quota is unavailable or exhausted. "
                "Check your API quota and try again later."
            )
        else:
            message = (
                "The AI service failed to complete this request. "
                "Please try again later."
            )

        return {"messages": [AIMessage(content=message)]}


def build_graph():
    graph = StateGraph(MessagesState)

    graph.add_node("reasoner", reason)
    graph.add_node("tools", ToolNode(TOOLS))

    graph.add_edge(START, "reasoner")

    graph.add_conditional_edges(
        "reasoner",
        tools_condition,
        {"tools": "tools", END: END},
    )

    graph.add_edge("tools", "reasoner")

    return graph.compile(checkpointer=MemorySaver())


agent = build_graph()


def ask_agent(
    question: str,
    thread_id: str = "local-session",
) -> str:
    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    session_token = set_audit_session(thread_id)

    record_audit(
        "user_question",
        status="received",
        question=question.strip(),
    )

    start = time.perf_counter()

    try:
        result = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": question.strip(),
                    }
                ]
            },
            config={
                "configurable": {"thread_id": thread_id},
                "recursion_limit": 12,
            },
        )

        answer = result["messages"][-1].content

        if isinstance(answer, str):
            final_answer = answer
        elif isinstance(answer, list):
            final_answer = "\n".join(
                block["text"]
                for block in answer
                if isinstance(block, dict) and block.get("text")
            )
        else:
            final_answer = str(answer)

        record_audit(
            "agent_response",
            status="success",
            duration_ms=round(
                (time.perf_counter() - start) * 1000, 2
            ),
            response=sanitize(final_answer)[:800],
        )

        return final_answer

    except Exception as error:
        record_audit(
            "agent_response",
            status="error",
            duration_ms=round(
                (time.perf_counter() - start) * 1000, 2
            ),
            error_type=type(error).__name__,
            error=sanitize(error),
        )
        raise

    finally:
        reset_audit_session(session_token)