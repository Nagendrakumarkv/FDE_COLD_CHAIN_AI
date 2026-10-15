
from agent.orchestrator import ask_agent


def main():
    session_a = "user-session-001"
    session_b = "user-session-002"

    conversation_a = [
        "My shipment ID is 102.",
        "What is its recorded temperature?",
        "What does the SOP recommend if that temperature exceeds the limit?",
    ]

    for question in conversation_a:
        print(f"\nUSER: {question}")
        try:
            print("AGENT:", ask_agent(question, session_a))
        except Exception as exc:
            print(f"ERROR: {type(exc).__name__}: {exc}")

    # A different session must not inherit session A's messages.
    print("\n--- Separate session test ---")
    try:
        print(
            "AGENT:",
            ask_agent("What shipment were we discussing?", session_b),
        )
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
