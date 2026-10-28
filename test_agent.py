import json
from pathlib import Path

from agent.orchestrator import ask_agent

AUDIT_LOG = Path("logs/agent_audit.jsonl")


def main():
    thread_id = "lesson-14-audit-test"

    questions = [
        "How many records are in the logistics table and What is the current weather in Los Angeles",
    ]

    for question in questions:
        print("\n" + "=" * 60)
        print(f"USER: {question}")

        try:
            answer = ask_agent(question, thread_id)
            print("AGENT:", answer)

        except Exception as error:
            print(
                f"ERROR: {type(error).__name__}: {error}"
            )

    print("\n--- AUDIT LOG CHECK ---")

    if not AUDIT_LOG.exists():
        print("Audit log not found:", AUDIT_LOG)
        return

    lines = AUDIT_LOG.read_text(
        encoding="utf-8"
    ).splitlines()

    print("Total audit events:", len(lines))

    for line in lines[-10:]:
        try:
            event = json.loads(line)
            print(
                event["timestamp"],
                event["session_id"],
                event["event_type"],
                event["status"],
            )
        except (json.JSONDecodeError, KeyError):
            print("Invalid audit record:", line[:200])


if __name__ == "__main__":
    main()