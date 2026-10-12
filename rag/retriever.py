
from sentence_transformers import SentenceTransformer

from rag.vector_store import get_collection

EMBEDDING_MODEL = "all-MiniLM-L6-v2"

model = SentenceTransformer(EMBEDDING_MODEL)


def search_sop(
    question: str,
    category: str | None = None,
    department: str | None = None,
    top_k: int = 3,
) -> list[dict]:
    if not question.strip():
        raise ValueError("Question cannot be empty.")

    if not 1 <= top_k <= 10:
        raise ValueError("top_k must be between 1 and 10.")

    filters = []

    if category:
        filters.append({"category": category})

    if department:
        filters.append({"department": department})

    where = None

    if len(filters) == 1:
        where = filters[0]
    elif len(filters) > 1:
        where = {"$and": filters}

    collection = get_collection()

    if collection.count() == 0:
        return []

    query_embedding = model.encode(
        [question],
        normalize_embeddings=True,
    ).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=min(top_k, collection.count()),
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    return [
        {
            "content": document,
            "source": metadata.get("source"),
            "category": metadata.get("category"),
            "department": metadata.get("department"),
            "distance": distance,
        }
        for document, metadata, distance
        in zip(documents, metadatas, distances)
    ]
