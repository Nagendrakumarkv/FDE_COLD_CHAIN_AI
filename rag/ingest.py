
import hashlib
from pathlib import Path

from sentence_transformers import SentenceTransformer

from rag.document_loader import load_document
from rag.chunker import create_chunks
from rag.vector_store import get_collection

DOCUMENTS_DIR = Path("documents")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def get_metadata(file: Path, index: int) -> dict:
    name = file.stem.lower()

    if "temperature" in name or "cold_chain" in name:
        category = "temperature"
    elif "emergency" in name:
        category = "emergency"
    elif "driver" in name:
        category = "driver_safety"
    else:
        category = "general"

    return {
        "source": file.name,
        "file_type": file.suffix.lower().lstrip("."),
        "category": category,
        "department": "operations",
        "chunk_index": index,
    }


def make_chunk_id(
    filename: str,
    index: int,
    content: str,
) -> str:
    digest = hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()[:16]

    return f"{filename}-{index}-{digest}"


def main():
    model = SentenceTransformer(EMBEDDING_MODEL)
    collection = get_collection()

    files = [
        path for path in DOCUMENTS_DIR.rglob("*")
        if path.is_file()
        and path.suffix.lower() in {
            ".txt", ".md", ".pdf", ".csv"
        }
    ]

    if not files:
        print("No supported documents found.")
        return

    total = 0

    for file in files:
        print(f"Processing: {file}")

        content = load_document(str(file))
        chunks = create_chunks(content)

        if not chunks:
            print("No text extracted; skipping.")
            continue

        # Remove old chunks for this source.
        collection.delete(
            where={"source": file.name}
        )

        embeddings = model.encode(
            chunks,
            normalize_embeddings=True,
        ).tolist()

        ids = [
            make_chunk_id(file.name, i, chunk)
            for i, chunk in enumerate(chunks)
        ]

        metadatas = [
            get_metadata(file, i)
            for i in range(len(chunks))
        ]

        collection.upsert(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        total += len(chunks)
        print(f"Stored {len(chunks)} chunks.")

    print(f"Ingestion complete: {total} chunks.")


if __name__ == "__main__":
    main()
