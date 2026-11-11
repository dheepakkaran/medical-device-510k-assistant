"""Deterministic citation check: every quote must appear word for word in the passage it cites."""
import re

def norm(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("­", "")
    return re.sub(r"\s+", " ", s).strip().lower()


def check(result: dict, passages: dict[int, dict]) -> tuple[bool, list[str]]:
    """Return (ok, problems). passages: id -> passage row."""
    problems = []
    if not result.get("found"):
        return True, []
    cites = result.get("citations") or []
    if not cites:
        problems.append("answer has no citations")
    for c in cites:
        p = passages.get(c.get("passage_id"))
        if p is None:
            problems.append(f"cites unknown passage {c.get('passage_id')}")
        elif len(norm(c.get("quote", "")).split()) < 5:
            problems.append(f"quote too short in passage {c['passage_id']}")
        elif norm(c["quote"]) not in norm(p["text"]):
            problems.append(f"quote not found word for word in passage {c['passage_id']}")
    return not problems, problems
