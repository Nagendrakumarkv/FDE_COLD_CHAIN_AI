import chromadb

from sentence_transformers import SentenceTransformer


CHROMA_PATH = "vector_db"
COLLECTION_NAME = "cold_chain_sop"


print("Loading embedding model...")

model = SentenceTransformer(
    "all-MiniLM-L6-v2"
)

print("Connecting to Chroma...")

client = chromadb.PersistentClient(
    path=CHROMA_PATH
)

collection = client.get_collection(
    name=COLLECTION_NAME
)

print("Chroma connected.")
print("Collection count:", collection.count())


def search_sop(
    question: str,
    top_k: int = 3,
) -> list[dict]:

    print("Creating query embedding...")

    query_embedding = model.encode(
        [question]
    ).tolist()[0]

    print("Embedding created.")
    print("Querying Chroma...")

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=[
            "documents",
            "metadatas",
        ],
    )

    print("Chroma query completed.")

    documents = results.get(
        "documents",
        [[]],
    )[0]

    metadatas = results.get(
        "metadatas",
        [[]],
    )[0]

    output = []

    for document, metadata in zip(
        documents,
        metadatas,
    ):
        metadata = metadata or {}

        output.append(
            {
                "source": metadata.get(
                    "source",
                    "unknown",
                ),
                "chunk_index": metadata.get(
                    "chunk_index",
                    -1,
                ),
                "content": document,
            }
        )

    print("output:", output)

    return output