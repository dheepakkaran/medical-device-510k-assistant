"""ETL: 3 public FDA guidance PDFs -> page text -> ~150-word chunks (page kept) -> bge-small embeddings -> guidance_chunks."""
import re, sys
from pathlib import Path
import pypdf
from fastembed import TextEmbedding

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.db import connect, init_schema

DOCS = {
    "se":  ("The 510(k) Program: Evaluating Substantial Equivalence (2014)", "https://www.fda.gov/media/82395/download"),
    "rta": ("Refuse to Accept Policy for 510(k)s (2022)", "https://www.fda.gov/media/83888/download"),
    "swf": ("Content of Premarket Submissions for Device Software Functions (2023)", "https://www.fda.gov/media/153781/download"),
}
WORDS, OVERLAP = 150, 30
EMBED_MODEL = "BAAI/bge-small-en-v1.5"


def clean(t: str) -> str:
    t = t.replace("Contains Nonbinding Recommendations", " ")
    t = re.sub(r"-\n(\w)", r"\1", t)          # re-join hyphenated line breaks
    return re.sub(r"\s+", " ", t).strip()


def chunk_pages(path: Path):
    for i, page in enumerate(pypdf.PdfReader(path).pages, start=1):
        words = clean(page.extract_text() or "").split()
        if len(words) < 20:
            continue
        step = WORDS - OVERLAP
        for s in range(0, max(len(words) - OVERLAP, 1), step):
            yield i, " ".join(words[s:s + WORDS])


def main():
    conn = connect(); init_schema(conn)
    conn.execute("TRUNCATE guidance_chunks RESTART IDENTITY")
    rows = [(d, title, p, txt) for d, (title, _) in DOCS.items()
            for p, txt in chunk_pages(Path(f"data/guidance/{d}.pdf"))]
    model = TextEmbedding(EMBED_MODEL)
    vecs = list(model.embed([r[3] for r in rows], batch_size=64))
    with conn.cursor() as cur:
        cur.executemany("INSERT INTO guidance_chunks (doc_id, doc_title, page, text, embedding) VALUES (%s,%s,%s,%s,%s)",
                        [(*r, v) for r, v in zip(rows, vecs)])
    for d in DOCS:
        n = conn.execute("SELECT count(*), count(DISTINCT page) FROM guidance_chunks WHERE doc_id=%s", (d,)).fetchone()
        print(d, "chunks", n[0], "pages", n[1])


if __name__ == "__main__":
    main()
