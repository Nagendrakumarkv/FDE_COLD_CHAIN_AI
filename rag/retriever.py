import chromadb

from sentence_transformers import SentenceTransformer


CHROMA_PATH = "vector_db"

COLLECTION_NAME = "cold_chain_sop"


model = SentenceTransformer(
    "all-MiniLM-L6-v2"
)

client = chromadb.PersistentClient(
    path=CHROMA_PATH
)

collection = client.get_collection(
    name=COLLECTION_NAME
)


def search_sop(
    question: str,
    top_k: int = 3,
) -> list[str]:

    query_embedding = model.encode(
        [question]
    ).tolist()[0]

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
    )

    return results["documents"][0]