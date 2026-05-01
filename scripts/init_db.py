import os
from urllib.parse import urlparse, unquote
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from db.database import engine, Base, DATABASE_URL
from db.models import User, Project, RuleStore, ComplianceEvent, EscalationEvent
from db.vector_store import ClauseEmbedding

def init_db():
    # Parse DATABASE_URL using urllib for safe handling of special chars
    parsed = urlparse(DATABASE_URL)
    db_name = parsed.path.lstrip("/")
    user = unquote(parsed.username or "postgres")
    password = unquote(parsed.password or "")
    host = parsed.hostname or "localhost"
    port = str(parsed.port or 5432)

    # Connect to default postgres database to create the new database if it doesn't exist
    print(f"Connecting to default postgres database to ensure '{db_name}' exists...")
    try:
        conn = psycopg2.connect(
            dbname="postgres",
            user=user,
            password=password,
            host=host,
            port=port
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{db_name}'")
        exists = cur.fetchone()
        if not exists:
            cur.execute(f"CREATE DATABASE {db_name}")
            print(f"Database '{db_name}' created.")
        else:
            print(f"Database '{db_name}' already exists.")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error checking/creating database: {e}")

    # Connect to the target database and ensure pgvector exists
    print(f"Connecting to '{db_name}' to enable pgvector...")
    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=user,
            password=password,
            host=host,
            port=port
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        print("Extension 'vector' enabled.")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error enabling pgvector extension: {e}")

    # Create all tables using SQLAlchemy
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")

if __name__ == "__main__":
    init_db()
