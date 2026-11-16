
import os

import pandas as pd

from dotenv import load_dotenv
from sqlalchemy import create_engine
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


engine = create_engine(
    get_database_url(),
    pool_pre_ping=True,
)

df = pd.read_csv("data/logistics.csv")

print(f"Rows loaded from CSV: {len(df)}")

# 'fail' prevents accidentally dropping or replacing an existing table.
df.to_sql(
    "logistics",
    engine,
    if_exists="fail",
    index=False,
)

print("Logistics data ingestion completed.")
