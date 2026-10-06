import os
import re

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()


DATABASE_URL = (
    f"postgresql+psycopg2://"
    f"{os.getenv('DB_USER')}:"
    f"{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:"
    f"{os.getenv('DB_PORT')}/"
    f"{os.getenv('DB_NAME')}"
)

engine = create_engine(DATABASE_URL)


FORBIDDEN_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "GRANT",
    "REVOKE",
    "MERGE",
    "COPY",
}


def validate_sql(query: str) -> None:
    """
    Validate SQL before sending it to PostgreSQL.
    """

    if not query or not query.strip():
        raise ValueError("SQL query cannot be empty.")

    cleaned_query = query.strip()

    # Must start with SELECT or WITH
    if not re.match(r"^(SELECT|WITH)\b", cleaned_query, re.IGNORECASE):
        raise ValueError(
            "Only SELECT or WITH queries are allowed."
        )

    # Remove SQL comments
    query_without_comments = re.sub(
        r"--.*?$|/\*.*?\*/",
        "",
        cleaned_query,
        flags=re.MULTILINE | re.DOTALL,
    )

    # Check dangerous keywords
    words = set(
        re.findall(
            r"\b[A-Z]+\b",
            query_without_comments.upper(),
        )
    )

    dangerous = words.intersection(FORBIDDEN_KEYWORDS)

    if dangerous:
        raise ValueError(
            f"Forbidden SQL operation detected: {', '.join(dangerous)}"
        )

    # Prevent multiple SQL statements
    statements = [
        statement.strip()
        for statement in query_without_comments.split(";")
        if statement.strip()
    ]

    if len(statements) > 1:
        raise ValueError(
            "Multiple SQL statements are not allowed."
        )


def execute_sql(query: str):
    """
    Validate and execute a read-only SQL query.
    """

    validate_sql(query)

    with engine.connect() as connection:

        # Start explicit read-only transaction
        connection.execute(
            text("BEGIN TRANSACTION READ ONLY")
        )

        try:
            result = connection.execute(text(query))

            rows = [
                dict(row._mapping)
                for row in result
            ]

            connection.commit()

            return rows

        except Exception:
            connection.rollback()
            raise