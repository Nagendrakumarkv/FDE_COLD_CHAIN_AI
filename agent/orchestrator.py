
import os

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

SYSTEM_PROMPT = """
You are a Cold Chain Logistics AI Assistant.

Available tools:
1. query_logistics: query logistics data using read-only SQL.
2. check_weather: retrieve current weather for a location.
3. search_compliance_sop: search company SOP and compliance documents.

Rules:
- Use tools when answers require database, weather, or SOP information.
- Never invent database results, weather readings, or SOP clauses.
- Use only existing database columns.
- SQL must be read-only.
- If a tool fails, report the limitation clearly.
- Cite the SOP source filename when using SOP results.
- Ask for clarification if a request is ambiguous.
- Never declare cargo safe using incomplete evidence.
- Keep answers concise and factual.
"""


@tool
def query_logistics(sql_query: str) -> list[dict]:
    """Run a read-only SQL SELECT query against logistics data."""
    return execute_sql(sql_query)


@tool
def check_weather(location: str) -> dict:
    """Get current weather for a named city or location."""
    return get_weather(location)


@tool
def search_compliance_sop(question: str) -> list[dict]:
    """Search company SOP and compliance documents."""
    return search_sop(question, top_k=3)


TOOLS = [
    query_logistics,
    check_weather,
    search_compliance_sop,
]


def create_model():
    """Initialize Gemini and enable tool calling."""
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY is missing. Add your Gemini API key to .env."
        )

    model_name = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

    model = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=0,
        max_retries=2,
    )

    return model.bind_tools(TOOLS)


model_with_tools = create_model()


def reason(state: MessagesState):
    """Ask Gemini to answer or request a tool call."""
    response = model_with_tools.invoke(
        [SystemMessage(content=SYSTEM_PROMPT)]
        + state["messages"]
    )
    return {"messages": [response]}


def build_graph():
    """Build the LangGraph reasoning and tool-execution loop."""
    builder = StateGraph(MessagesState)

    builder.add_node("reasoner", reason)
    builder.add_node("tools", ToolNode(TOOLS))

    builder.add_edge(START, "reasoner")

    builder.add_conditional_edges(
        "reasoner",
        tools_condition,
        {
            "tools": "tools",
            END: END,
        },
    )

    builder.add_edge("tools", "reasoner")

    # Conversation memory exists only while this process is running.
    checkpointer = MemorySaver()

    return builder.compile(checkpointer=checkpointer)


agent = build_graph()


def ask_agent(
    question: str,
    thread_id: str = "local-session",
) -> str:
    """Run one question through the Gemini-powered agent."""
    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    result = agent.invoke(
        {
            "messages": [
                {"role": "user", "content": question.strip()}
            ]
        },
        config={
            "configurable": {
                "thread_id": thread_id,
            }
        },
    )

    answer = result["messages"][-1].content

    if isinstance(answer, str):
        return answer

    # Handle Gemini responses represented as content blocks.
    if isinstance(answer, list):
        return "\n".join(
            str(block.get("text", ""))
            for block in answer
            if isinstance(block, dict) and block.get("text")
        )

    return str(answer)
