from pathlib import Path

import pandas as pd
from pypdf import PdfReader


def load_txt(path: Path) -> str:
    return path.read_text(
        encoding="utf-8"
    )


def load_markdown(path: Path) -> str:
    return path.read_text(
        encoding="utf-8"
    )


def load_pdf(path: Path) -> str:
    reader = PdfReader(str(path))

    pages = []

    for page in reader.pages:
        text = page.extract_text()

        if text:
            pages.append(text)

    return "\n\n".join(pages)


def load_csv(path: Path) -> str:
    df = pd.read_csv(path)

    rows = []

    for row in df.to_dict(
        orient="records"
    ):
        rows.append(
            "\n".join(
                f"{key}: {value}"
                for key, value in row.items()
            )
        )

    return "\n\n".join(rows)


def load_document(path: str) -> str:

    file_path = Path(path)

    extension = file_path.suffix.lower()

    if extension == ".txt":
        return load_txt(file_path)

    if extension == ".md":
        return load_markdown(file_path)

    if extension == ".pdf":
        return load_pdf(file_path)

    if extension == ".csv":
        return load_csv(file_path)

    raise ValueError(
        f"Unsupported file type: {extension}"
    )