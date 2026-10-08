from rag.retriever import search_sop


def main():
    question = (
        "What should we do if "
        "refrigerated cargo exceeds 8 degrees?"
    )

    print("\nSearching SOP...")
    print("-" * 50)

    try:
        results = search_sop(
            question,
            top_k=3,
        )

        print("\nRelevant SOP Documents")
        print("=" * 50)

        if not results:
            print("No results found.")
            return

        for index, result in enumerate(
            results,
            start=1,
        ):
            print(f"\nResult {index}")
            print("-" * 50)

            print(
                f"Source: {result.get('source', 'unknown')}"
            )

            print(
                f"Chunk: {result.get('chunk_index', -1)}"
            )

            print("Content:")
            print(
                result.get(
                    "content",
                    "",
                )
            )

    except Exception as error:
        print("\nRAG search failed:")
        print(error)


if __name__ == "__main__":
    main()