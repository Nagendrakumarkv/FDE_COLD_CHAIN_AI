
import os
import re

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

load_dotenv()


def get_database_url():
    """Return the database URL for local PostgreSQL or Neon."""

    db_target = os.getenv("DB_TARGET", "local").lower()

    if db_target == "neon":
        database_url = os.getenv("DATABASE_URL")

        if not database_url:
            raise ValueError("DATABASE_URL is missing from .env")

        url = make_url(database_url)

        # Ensure the PostgreSQL psycopg2 driver is used.
        if url.drivername in ("postgres", "postgresql"):
            url = url.set(drivername="postgresql+psycopg2")

        return url

    if db_target == "local":
        required_vars = [
            "DB_HOST",
            "DB_PORT",
            "DB_NAME",
            "DB_USER",
            "DB_PASSWORD",
        ]

        missing = [
            variable for variable in required_vars
            if not os.getenv(variable)
        ]

        if missing:
            raise ValueError(
                f"Missing local database settings: {', '.join(missing)}"
            )

        return URL.create(
            drivername="postgresql+psycopg2",
            username=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT")),
            database=os.getenv("DB_NAME"),
        )

    raise ValueError("DB_TARGET must be 'local' or 'neon'.")


DATABASE_URL = get_database_url()

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


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


# Same rules as agent/security.py (tools must not import from agent/).
PROTECTED_TABLES = re.compile(
    r"\b(admin_users|conversations|conversation_messages)\b",
    re.IGNORECASE,
)

DYNAMIC_QUERY_FUNCTIONS = re.compile(
    r"\b(query_to_xml|query_to_xml_and_xmlschema|table_to_xml|"
    r"cursor_to_xml|database_to_xml|schema_to_xml)\s*\(",
    re.IGNORECASE,
)


def validate_sql(query: str) -> None:
    """Validate SQL before sending it to PostgreSQL."""

    if not query or not query.strip():
        raise ValueError("SQL query cannot be empty.")

    cleaned_query = query.strip()

    if not re.match(r"^(SELECT|WITH)\b", cleaned_query, re.IGNORECASE):
        raise ValueError("Only SELECT or WITH queries are allowed.")

    # Remove SQL comments.
    query_without_comments = re.sub(
        r"--[^\n]*|/\*.*?\*/",
        "",
        cleaned_query,
        flags=re.DOTALL,
    )

    words = set(
        re.findall(r"\b[A-Z]+\b", query_without_comments.upper())
    )

    dangerous = words.intersection(FORBIDDEN_KEYWORDS)

    if dangerous:
        raise ValueError(
            f"Forbidden SQL operation detected: {', '.join(sorted(dangerous))}"
        )

    # Admin credentials and chat history share this database but must
    # never be readable through the agent's SQL tool.
    if PROTECTED_TABLES.search(query_without_comments) or (
        DYNAMIC_QUERY_FUNCTIONS.search(query_without_comments)
    ):
        raise ValueError("Access to this table is not allowed.")

    statements = [
        statement.strip()
        for statement in query_without_comments.split(";")
        if statement.strip()
    ]

    if len(statements) > 1:
        raise ValueError("Multiple SQL statements are not allowed.")


def execute_sql(query: str):
    """Validate and execute a read-only SQL query."""

    validate_sql(query)

    with engine.connect() as connection:
        with connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))

            result = connection.execute(text(query))

            return [
                dict(row._mapping)
                for row in result
            ]
