from agent.orchestrator import ask_agent


def main():
    thread_id = "react-agent-test"

    questions = [
        "How many records are in the logistics table and What is the current weather in Los Angeles",
    ]

    for question in questions:
        print("\n" + "=" * 65)
        print(f"USER: {question}")

        try:
            answer = ask_agent(question, thread_id)
            print(f"AGENT: {answer}")

        except Exception as exc:
            print(f"ERROR: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()