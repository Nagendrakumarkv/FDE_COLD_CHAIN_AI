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
- Weather API: current weather conditions.
- ChromaDB RAG: company SOPs and compliance documents.

Failure-handling rules:
- Use actual tool results only.
- If a tool reports an error, do not invent its result.
- If another available tool can help, use it.
- Clearly disclose missing evidence and failed tools.
- Never claim cargo is safe from incomplete evidence.
- Cite SOP source filenames when available.
- Never bypass SQL validation.
- Keep answers concise and factual.
"""


def is_transient_error(error: Exception) -> bool:
    """Identify errors that may succeed on a later attempt."""
    status_code = getattr(error, "status_code", None)

    if status_code in (500, 502, 503, 504):
        return True

    name = type(error).__name__.lower()
    message = str(error).lower()

    # Do not retry exhausted quotas or authentication failures.
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
        "connection refused",
        "service unavailable",
        "internal server error",
        "bad gateway",
    )

    return (
        any(item in name for item in transient_names)
        or any(item in message for item in transient_messages)
    )


@tool
def query_logistics(sql_query: str) -> dict:
    """Query logistics records using validated, read-only SQL."""
    try:
        return {"data": execute_sql(sql_query)}
    except Exception:
        logger.exception("Logistics SQL tool failed")
        return {
            "error": (
                "The logistics database query failed. "
                "No database result is available."
            )
        }


@tool
def check_weather(location: str) -> dict:
    """Retrieve current weather for a named location."""
    try:
        return {"data": get_weather(location)}
    except Exception:
        logger.exception("Weather tool failed")
        return {
            "error": (
                "The weather service is currently unavailable "
                "or the request failed."
            )
        }


@tool
def search_compliance_sop(question: str) -> dict:
    """Search company SOP and compliance documents."""
    try:
        return {"data": search_sop(question, top_k=3)}
    except Exception:
        logger.exception("SOP retrieval failed")
        return {
            "error": (
                "The SOP search failed. No verified policy "
                "evidence is available from this search."
            )
        }


TOOLS = [
    query_logistics,
    check_weather,
    search_compliance_sop,
]


def create_model():
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY is missing from the .env file."
        )

    return ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        google_api_key=api_key,
        temperature=0,
        max_retries=0,
    ).bind_tools(TOOLS)


model_with_tools = create_model()


def invoke_model_with_retry(messages):
    """Retry only errors classified as transient."""
    max_attempts = 3

    for attempt in range(1, max_attempts + 1):
        try:
            return model_with_tools.invoke(messages)

        except Exception as error:
            if (
                attempt == max_attempts
                or not is_transient_error(error)
            ):
                raise

            delay = 2 ** (attempt - 1)

            logger.warning(
                "Transient Gemini error; retrying in %s seconds "
                "(attempt %s/%s).",
                delay,
                attempt,
                max_attempts,
            )

            time.sleep(delay)


def reason(state: MessagesState):
    """Ask Gemini to reason over the conversation and tool results."""
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        *state["messages"],
    ]

    try:
        response = invoke_model_with_retry(messages)
        return {"messages": [response]}

    except Exception as error:
        logger.exception("Gemini reasoning failed")

        # Return a clear response rather than crashing the graph.
        if "429" in str(error) or "quota" in str(error).lower():
            message = (
                "The Gemini API quota is unavailable or exhausted. "
                "Please check your API quota and try again later."
            )
        else:
            message = (
                "I couldn't complete the request because the AI "
                "service failed. Please try again later."
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
        {
            "tools": "tools",
            END: END,
        },
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
        return answer

    if isinstance(answer, list):
        return "\n".join(
            block["text"]
            for block in answer
            if isinstance(block, dict) and block.get("text")
        )

    return str(answer)