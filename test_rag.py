
from rag.retriever import search_sop


def main():
    question = (
        "What should happen if refrigerated "
        "cargo exceeds 8 degrees Celsius?"
    )

    results = search_sop(
        question=question,
        category="temperature",
        department="operations",
        top_k=3,
    )

    if not results:
        print("No matching SOP documents found.")
        return

    for index, result in enumerate(results, start=1):
        print(f"\nResult {index}")
        print(f"Source: {result['source']}")
        print(f"Category: {result['category']}")
        print(f"Distance: {result['distance']:.4f}")
        print(result["content"])


if __name__ == "__main__":
    main()
