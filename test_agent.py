
from agent.orchestrator import ask_agent


def main():
    thread_id = "cold-chain-gemini-demo"

    questions = [
        "How many records are in the logistics table?",
        "What is the current weather in Los Angeles?",
        "What does the SOP say about cargo above 8 degrees Celsius?",
    ]

    for question in questions:
        print("\n" + "=" * 65)
        print(f"USER: {question}")

        try:
            answer = ask_agent(
                question=question,
                thread_id=thread_id,
            )
            print(f"\nAGENT: {answer}")

        except Exception as error:
            print(f"\nERROR: {type(error).__name__}: {error}")


if __name__ == "__main__":
    main()
