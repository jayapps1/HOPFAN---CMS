import os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker


from src.config.environment import ENV_FILE, PROJECT_ROOT, load_environment

load_environment()


DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")


if not all([DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD]):
    raise RuntimeError(
        f"Missing database configuration. "
        f"Expected environment file: {ENV_FILE}"
    )


DATABASE_URL = URL.create(
    drivername="postgresql+psycopg",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=int(DB_PORT),
    database=DB_NAME,
)


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def test_database_connection():
    try:
        print(f"Environment file: {ENV_FILE}")
        print(f"Configured database: {DB_NAME}")
        print(f"Configured user: {DB_USER}")

        with engine.connect() as connection:
            result = connection.execute(
                text(
                    """
                    SELECT
                        current_database() AS database_name,
                        current_user AS database_user
                    """
                )
            )

            row = result.fetchone()

            print("Database connection successful!")
            print(f"Database: {row.database_name}")
            print(f"User: {row.database_user}")

    except Exception as exc:
        print("Database connection failed!")
        print(exc)
