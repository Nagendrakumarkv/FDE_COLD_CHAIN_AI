
import chromadb

from rag.vector_store import get_collection

CHROMA_PATH = "vector_db"
COLLECTION_NAME = "cold_chain_sop"
BATCH_SIZE = 100


def main():
    print("Connecting to local ChromaDB...")

    local_client = chromadb.PersistentClient(
        path=CHROMA_PATH
    )

    local_collection = local_client.get_collection(
        name=COLLECTION_NAME
    )

    local_count = local_collection.count()

    print(f"Local Chroma records: {local_count}")

    if local_count == 0:
        print("No local records found. Migration stopped.")
        return

    print("Connecting to Qdrant Cloud...")

    qdrant_collection = get_collection()

    migrated = 0

    for offset in range(0, local_count, BATCH_SIZE):
        batch = local_collection.get(
            limit=BATCH_SIZE,
            offset=offset,
            include=[
                "documents",
                "metadatas",
                "embeddings",
            ],
        )

        ids = batch["ids"]
        documents = batch["documents"]
        metadatas = batch["metadatas"]
        embeddings = batch["embeddings"]

        if not ids:
            continue

        qdrant_collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings.tolist(),
            metadatas=metadatas,
        )

        migrated += len(ids)

        print(
            f"Migrated {migrated}/{local_count} records"
        )

    cloud_count = qdrant_collection.count()

    print("\nMigration completed.")
    print(f"Local records: {local_count}")
    print(f"Qdrant records: {cloud_count}")

    if cloud_count < local_count:
        raise RuntimeError(
            "Migration verification failed: "
            "Qdrant has fewer records than local ChromaDB."
        )


if __name__ == "__main__":
    main()
