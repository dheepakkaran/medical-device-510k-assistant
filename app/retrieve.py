"""Retrieval over FDA guidance chunks: keyword baseline (Postgres full-text), embedding (pgvector cosine), hybrid (RRF).
Settings fixed before the test run: top_k=5, bge-small-en-v1.5, RRF k=60. App default = hybrid (chosen before testing)."""
import re
from functools import lru_cache
from fastembed import TextEmbedding

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
COLS = "id, doc_id, doc_title, page, text"


@lru_cache(maxsize=1)
def _model():
    return TextEmbedding(EMBED_MODEL)


def embed(q: str):
    # bge recommends a query instruction prefix for short queries
    return next(iter(_model().embed(["Represent this sentence for searching relevant passages: " + q])))


def _rows(cur_rows):
    return [dict(zip(["id", "doc_id", "doc_title", "page", "text"], r)) for r in cur_rows]


def keyword(conn, q: str, k: int = 5):
    terms = [t for t in re.findall(r"[a-z0-9]+", q.lower()) if len(t) > 2]
    if not terms:
        return []
    tsq = " | ".join(terms)  # OR of terms, ranked by ts_rank (AND of all terms rarely matches a chunk)
    sql = (f"SELECT {COLS} FROM guidance_chunks, to_tsquery('english', %s) query "
           "WHERE tsv @@ query ORDER BY ts_rank(tsv, query) DESC LIMIT %s")
    return _rows(conn.execute(sql, (tsq, k)).fetchall())


def vector(conn, q: str, k: int = 5):
    sql = f"SELECT {COLS} FROM guidance_chunks ORDER BY embedding <=> %s LIMIT %s"
    return _rows(conn.execute(sql, (embed(q), k)).fetchall())


def hybrid(conn, q: str, k: int = 5, rrf_k: int = 60):
    lists = [keyword(conn, q, 20), vector(conn, q, 20)]
    score, by_id = {}, {}
    for lst in lists:
        for rank, r in enumerate(lst):
            score[r["id"]] = score.get(r["id"], 0) + 1 / (rrf_k + rank + 1)
            by_id[r["id"]] = r
    return [by_id[i] for i in sorted(score, key=score.get, reverse=True)[:k]]


METHODS = {"keyword": keyword, "vector": vector, "hybrid": hybrid}
