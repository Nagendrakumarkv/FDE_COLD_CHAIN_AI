
import os
import logging

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from tools.sql_tool import execute_sql
from tools.weather_tool import get_weather
from rag.retriever import search_sop

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are a Cold Chain Logistics AI Assistant.

Choose tools based on the question:
- Shipment counts, temperatures, delays, inventory: PostgreSQL SQL tool.
- Current weather: Weather tool.
- Company policy and handling procedures: SOP search tool.
- Questions requiring multiple data sources: call multiple relevant tools.

Safety:
- Never invent SQL results, weather observations, or SOP content.
- Generate read-only SQL only; database permissions must enforce this.
- Use actual tool outputs as evidence.
- Cite SOP source filenames when available.
- If a tool fails or returns no evidence, disclose that limitation.
- Never declare cargo safe based on incomplete evidence.
- Distinguish measured facts from potential risks.
- Do not claim that an SOP was followed merely because it was retrieved.
- Answer concisely.
"""


def tool_error(tool_name: str, error: Exception) -> dict:
    logger.exception("%s failed", tool_name)
    return {
        "error": f"{tool_name} failed: {type(error).__name__}: {error}"
    }


@tool
def query_logistics(sql_query: str) -> dict:
    """Query logistics records using read-only SQL."""
    try:
        return {"data": execute_sql(sql_query)}
    except Exception as error:
        return tool_error("SQL query", error)


@tool
def check_weather(location: str) -> dict:
    """Get current weather for a named location."""
    try:
        return {"data": get_weather(location)}
    except Exception as error:
        return tool_error("Weather lookup", error)


@tool
def search_compliance_sop(question: str) -> dict:
    """Search company SOP and compliance documents."""
    try:
        return {"data": search_sop(question, top_k=3)}
    except Exception as error:
        return tool_error("SOP search", error)


TOOLS = [
    query_logistics,
    check_weather,
    search_compliance_sop,
]


def create_model():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Set GOOGLE_API_KEY in your .env file.")

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
    builder = StateGraph(MessagesState)
    builder.add_node("reasoner", reason)
    builder.add_node("tools", ToolNode(TOOLS))

    builder.add_edge(START, "reasoner")
    builder.add_conditional_edges(
        "reasoner",
        tools_condition,
        {"tools": "tools", END: END},
    )
    builder.add_edge("tools", "reasoner")

    return builder.compile(checkpointer=MemorySaver())


agent = build_graph()


def ask_agent(
    question: str,
    thread_id: str = "local-session",
) -> str:
    if not question or not question.strip():
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
