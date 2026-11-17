
import os
import uuid

import chromadb
from dotenv import load_dotenv
from qdrant_client import QdrantClient, models

load_dotenv()

COLLECTION_NAME = os.getenv(
    "QDRANT_COLLECTION",
    "cold_chain_sop",
)

VECTOR_SIZE = 384


def get_provider():
    return os.getenv("VECTOR_DB_PROVIDER", "chroma").lower()


def get_chroma_client():
    return chromadb.PersistentClient(
        path=os.getenv("CHROMA_PATH", "vector_db")
    )


def get_qdrant_client():
    url = os.getenv("QDRANT_URL")
    api_key = os.getenv("QDRANT_API_KEY")

    if not url or not api_key:
        raise ValueError(
            "QDRANT_URL and QDRANT_API_KEY must be configured."
        )

    return QdrantClient(
        url=url,
        api_key=api_key,
        timeout=60,
    )



def get_qdrant_collection():
    client = get_qdrant_client()

    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=VECTOR_SIZE,
                distance=models.Distance.COSINE,
            ),
        )

    # Create indexes for metadata filtering.
    for field in [
        "metadata.source",
        "metadata.category",
        "metadata.department",
    ]:
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name=field,
            field_schema=models.PayloadSchemaType.KEYWORD,
            wait=True,
        )

    return client

def make_point_id(original_id):
    """Convert any string ID into a stable Qdrant UUID."""
    return str(
        uuid.uuid5(uuid.NAMESPACE_URL, str(original_id))
    )


def convert_filter(where):
    """Convert simple Chroma metadata filters to Qdrant filters."""

    if not where:
        return None

    if "$and" in where:
        return models.Filter(
            must=[
                convert_filter(condition).must[0]
                for condition in where["$and"]
            ]
        )

    conditions = []

    for key, value in where.items():
        conditions.append(
            models.FieldCondition(
                key=f"metadata.{key}",
                match=models.MatchValue(value=value),
            )
        )

    return models.Filter(must=conditions)


class QdrantCollection:

    def __init__(self):
        self.client = get_qdrant_collection()

    def count(self):
        result = self.client.count(
            collection_name=COLLECTION_NAME,
            exact=True,
        )
        return result.count

    def upsert(
        self,
        ids,
        documents,
        embeddings,
        metadatas,
    ):
        points = []

        for original_id, document, embedding, metadata in zip(
            ids, documents, embeddings, metadatas
        ):
            points.append(
                models.PointStruct(
                    id=make_point_id(original_id),
                    vector=embedding,
                    payload={
                        "original_id": str(original_id),
                        "document": document,
                        "metadata": metadata or {},
                    },
                )
            )

        if points:
            self.client.upsert(
                collection_name=COLLECTION_NAME,
                points=points,
                wait=True,
            )

    def delete(self, where):
        query_filter = convert_filter(where)

        if query_filter:
            self.client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=models.FilterSelector(
                    filter=query_filter
                ),
                wait=True,
            )

    def query(
        self,
        query_embeddings,
        n_results=3,
        where=None,
        include=None,
    ):
        response = self.client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_embeddings[0],
            query_filter=convert_filter(where),
            limit=n_results,
            with_payload=True,
            with_vectors=False,
        )

        points = response.points

        return {
            "ids": [[point.payload.get("original_id") for point in points]],
            "documents": [[point.payload.get("document") for point in points]],
            "metadatas": [[point.payload.get("metadata", {}) for point in points]],
            # Convert cosine similarity into cosine distance.
            "distances": [[1.0 - point.score for point in points]],
        }


def get_collection():
    provider = get_provider()

    if provider == "qdrant":
        return QdrantCollection()

    if provider == "chroma":
        client = get_chroma_client()

        return client.get_or_create_collection(
            name="cold_chain_sop",
            metadata={"hnsw:space": "cosine"},
        )

    raise ValueError(
        "VECTOR_DB_PROVIDER must be 'chroma' or 'qdrant'."
    )
