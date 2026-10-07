from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer


DOCUMENT_PATH = Path("documents/cold_chain_sop.txt")

CHROMA_PATH = "vector_db"

COLLECTION_NAME = "cold_chain_sop"


def load_document() -> str:
    return DOCUMENT_PATH.read_text(
        encoding="utf-8"
    )


def create_chunks(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[str]:

    chunks = []

    start = 0

    while start < len(text):

        end = start + chunk_size

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start = end - overlap

    return chunks


def main():

    print("Loading SOP...")

    text = load_document()

    chunks = create_chunks(text)

    print(f"Created {len(chunks)} chunks.")

    print("Loading embedding model...")

    model = SentenceTransformer(
        "all-MiniLM-L6-v2"
    )

    print("Connecting to Chroma...")

    client = chromadb.PersistentClient(
        path=CHROMA_PATH
    )

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME
    )

    embeddings = model.encode(
        chunks
    ).tolist()

    ids = [
        f"sop-{index}"
        for index in range(len(chunks))
    ]

    collection.upsert(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
    )

    print("SOP ingestion completed.")


if __name__ == "__main__":
    main()