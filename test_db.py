from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()

db_url = (
    f"postgresql+psycopg2://"
    f"{os.getenv('DB_USER')}:"
    f"{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:"
    f"{os.getenv('DB_PORT')}/"
    f"{os.getenv('DB_NAME')}"
)

engine = create_engine(db_url)

with engine.connect() as conn:
    result = conn.execute(
        text("""
            SELECT
                current_user,
                current_database(),
                inet_server_addr(),
                inet_server_port(),
                has_schema_privilege(
                    current_user,
                    'public',
                    'CREATE'
                )
        """)
    )

    print(result.fetchone())