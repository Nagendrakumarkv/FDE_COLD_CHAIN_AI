from rag.retriever import search_sop


def main():

    question = (
        "What is the acceptable temperature "
        "range for refrigerated healthcare cargo?"
    )

    documents = search_sop(question)

    print("\nRelevant SOP Information")
    print("=" * 40)

    for index, document in enumerate(
        documents,
        start=1,
    ):
        print(f"\nResult {index}")
        print("-" * 40)
        print(document)


if __name__ == "__main__":
    main()