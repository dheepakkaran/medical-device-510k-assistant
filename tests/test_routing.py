"""Cascade logic with a fake model call (no API spend)."""
from app import answer as ans

PASSAGES = [{"id": 1, "doc_id": "rta", "doc_title": "RTA", "page": 5,
             "text": "FDA will inform the submitter within the first 15 calendar days after receipt."}]
GOOD = {"found": True, "answer": "15 days.", "citations": [{"passage_id": 1, "quote": "within the first 15 calendar days after receipt"}]}
BAD = {"found": True, "answer": "30 days.", "citations": [{"passage_id": 1, "quote": "within the first 30 calendar days after receipt"}]}


def fake(responses, calls):
    def _call(model, q, ps, tag):
        calls.append(model)
        return dict(responses[model])
    return _call


def test_cheap_model_verified_no_escalation(monkeypatch):
    calls = []
    monkeypatch.setattr(ans, "_call", fake({ans.CHEAP: GOOD, ans.STRONG: GOOD}, calls))
    r = ans.answer("q", PASSAGES)
    assert r["verified"] and calls == [ans.CHEAP]
    assert r["citations"][0]["page"] == 5


def test_bad_quote_escalates_to_strong(monkeypatch):
    calls = []
    monkeypatch.setattr(ans, "_call", fake({ans.CHEAP: BAD, ans.STRONG: GOOD}, calls))
    r = ans.answer("q", PASSAGES)
    assert r["verified"] and calls == [ans.CHEAP, ans.STRONG]


def test_both_fail_returns_no_answer(monkeypatch):
    calls = []
    monkeypatch.setattr(ans, "_call", fake({ans.CHEAP: BAD, ans.STRONG: BAD}, calls))
    r = ans.answer("q", PASSAGES)
    assert not r["found"] and r["citations"] == [] and not r["verified"]
