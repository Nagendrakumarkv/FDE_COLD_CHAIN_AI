from agent.orchestrator import ask_agent


def test_empty_question():
    try:
        ask_agent("")
    except ValueError as error:
        print("PASS: Empty question rejected:", error)
    else:
        print("FAIL: Empty question was accepted")


def main():
    test_empty_question()

    questions = [
        "How many records are in the logistics table and What is the current weather in Los Angeles",
    ]

    for index, question in enumerate(questions, start=1):
        print("\n" + "=" * 60)
        print(f"TEST {index}: {question}")

        try:
            answer = ask_agent(
                question=question,
                thread_id=f"error-test-{index}",
            )
            print("RESULT:", answer)

        except Exception as error:
            print(
                f"UNHANDLED ERROR: "
                f"{type(error).__name__}: {error}"
            )


if __name__ == "__main__":
    main()