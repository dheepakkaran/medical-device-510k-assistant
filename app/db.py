"""Database connection + schema. Local Postgres (scripts/db.sh) or DATABASE_URL."""
import os
import psycopg
from pgvector.psycopg import register_vector

DSN = os.getenv("DATABASE_URL", "postgresql://postgres@localhost:5433/md510k")

SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS devices (
    k_number       text PRIMARY KEY,
    device_name    text NOT NULL,
    applicant      text,
    product_code   text NOT NULL,
    decision_date  date,
    decision       text,
    clearance_type text,
    advisory_committee text
);
CREATE INDEX IF NOT EXISTS devices_code ON devices (product_code);
CREATE TABLE IF NOT EXISTS guidance_chunks (
    id        serial PRIMARY KEY,
    doc_id    text NOT NULL,
    doc_title text NOT NULL,
    page      int  NOT NULL,
    text      text NOT NULL,
    tsv       tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    embedding vector(384)
);
CREATE INDEX IF NOT EXISTS chunks_tsv ON guidance_chunks USING gin (tsv);
"""


def connect():
    conn = psycopg.connect(DSN, autocommit=True)
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    register_vector(conn)
    return conn


def init_schema(conn):
    conn.execute(SCHEMA)
