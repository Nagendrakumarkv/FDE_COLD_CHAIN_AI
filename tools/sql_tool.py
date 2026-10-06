import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

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


def execute_sql(query: str):
    """Execute a read-only SQL query."""

    if not query.strip().lower().startswith("select"):
        raise ValueError("Only SELECT queries are allowed.")

    with engine.connect() as connection:
        connection = connection.execution_options(
            isolation_level="AUTOCOMMIT"
        )

        result = connection.execute(text(query))

        return [dict(row._mapping) for row in result]