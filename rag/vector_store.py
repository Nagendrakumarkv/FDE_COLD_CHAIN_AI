
import os

import chromadb
from dotenv import load_dotenv

load_dotenv()


def get_chroma_client():
    host = os.getenv("CHROMA_HOST")

    if host:
        return chromadb.HttpClient(
            host=host,
            port=int(os.getenv("CHROMA_PORT", "8000")),
        )

    return chromadb.PersistentClient(
        path=os.getenv("CHROMA_PATH", "vector_db")
    )


def get_collection():
    client = get_chroma_client()

    return client.get_or_create_collection(
        name="cold_chain_sop",
        metadata={"hnsw:space": "cosine"},
    )
