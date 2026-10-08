from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

from rag.document_loader import load_document
from rag.chunker import create_chunks


DOCUMENTS_DIR = Path("documents")

CHROMA_PATH = "vector_db"

COLLECTION_NAME = "cold_chain_sop"


def main():

    print("Loading embedding model...")

    model = SentenceTransformer(
        "all-MiniLM-L6-v2"
    )

    client = chromadb.PersistentClient(
        path=CHROMA_PATH
    )

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME
    )

    files = [
        file
        for file in DOCUMENTS_DIR.iterdir()
        if file.is_file()
    ]

    total_chunks = 0

    for file in files:

        print(
            f"\nProcessing: {file.name}"
        )

        try:
            text = load_document(
                str(file)
            )

            chunks = create_chunks(text)

            print(
                f"Created {len(chunks)} chunks"
            )

            embeddings = model.encode(
                chunks
            ).tolist()

            ids = [
                f"{file.stem}-{index}"
                for index in range(len(chunks))
            ]

            metadatas = [
                {
                    "source": file.name,
                    "chunk_index": index,
                }
                for index in range(len(chunks))
            ]

            collection.upsert(
                ids=ids,
                documents=chunks,
                embeddings=embeddings,
                metadatas=metadatas,
            )

            total_chunks += len(chunks)

        except Exception as error:

            print(
                f"Failed: {file.name}"
            )

            print(error)

    print(
        f"\nIngestion completed."
    )

    print(
        f"Total chunks: {total_chunks}"
    )


if __name__ == "__main__":
    main()