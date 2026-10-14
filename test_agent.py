
from agent.orchestrator import ask_agent


def main():
    thread_id = "lesson-10-test"

    questions = [
        "How many records are in the logistics table?",
        # "What is the current weather in Los Angeles?",
        # "What does our SOP say about cargo above 8 degrees Celsius?",
        # (
        #     "Find shipments with recorded cargo temperatures above "
        #     "8 degrees Celsius and retrieve the relevant SOP guidance. "
        #     "Report the shipment evidence and policy separately."
        # ),
    ]

    for question in questions:
        print("\n" + "=" * 70)
        print(f"USER: {question}")

        try:
            print("AGENT:", ask_agent(question, thread_id=thread_id))
        except Exception as error:
            print(f"ERROR: {type(error).__name__}: {error}")


if __name__ == "__main__":
    main()
