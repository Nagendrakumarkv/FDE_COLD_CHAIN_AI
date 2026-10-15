
import os
import logging

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
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
Use SQL for logistics data, weather for current conditions,
and SOP search for company procedures.

Use conversation history to resolve references such as "it",
"that shipment", and "what about the previous one".
Never invent results. Disclose tool failures.
Cite SOP source filenames when available.
Never declare cargo safe using incomplete evidence.
Keep answers concise and factual.
"""


@tool
def query_logistics(sql_query: str) -> dict:
    """Query logistics records using read-only SQL."""
    try:
        return {"data": execute_sql(sql_query)}
    except Exception as exc:
        logger.exception("SQL tool failed")
        return {"error": f"SQL query failed: {exc}"}


@tool
def check_weather(location: str) -> dict:
    """Get current weather for a location."""
    try:
        return {"data": get_weather(location)}
    except Exception as exc:
        logger.exception("Weather tool failed")
        return {"error": f"Weather lookup failed: {exc}"}


@tool
def search_compliance_sop(question: str) -> dict:
    """Search company SOP and compliance documents."""
    try:
        return {"data": search_sop(question, top_k=3)}
    except Exception as exc:
        logger.exception("SOP tool failed")
        return {"error": f"SOP search failed: {exc}"}


TOOLS = [
    query_logistics,
    check_weather,
    search_compliance_sop,
]


def create_model():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is missing from .env")

    model = ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        google_api_key=api_key,
        temperature=0,
        max_retries=2,
    )
    return model.bind_tools(TOOLS)


model_with_tools = create_model()


def reason(state: MessagesState):
    response = model_with_tools.invoke(
        [SystemMessage(content=SYSTEM_PROMPT)]
        + state["messages"]
    )
    return {"messages": [response]}


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

    # Stores conversation checkpoints in process memory.
    return graph.compile(checkpointer=MemorySaver())


agent = build_graph()


def ask_agent(
    question: str,
    thread_id: str = "local-session",
) -> str:
    if not question.strip():
        raise ValueError("Question cannot be empty.")

    result = agent.invoke(
        {"messages": [{"role": "user", "content": question.strip()}]},
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
