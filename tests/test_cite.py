from app.cite import check

P = {7: {"text": "FDA will inform the submitter within the first 15 calendar days after receipt of the submission."}}


def test_verbatim_quote_passes_even_with_spacing_and_curly_quotes():
    r = {"found": True, "citations": [{"passage_id": 7, "quote": "within the first  15 calendar days after receipt"}]}
    assert check(r, P) == (True, [])


def test_changed_word_fails():
    r = {"found": True, "citations": [{"passage_id": 7, "quote": "within the first 30 calendar days after receipt"}]}
    ok, probs = check(r, P)
    assert not ok and "word for word" in probs[0]


def test_unknown_passage_and_missing_citation_fail():
    assert not check({"found": True, "citations": [{"passage_id": 99, "quote": "within the first 15 calendar days"}]}, P)[0]
    assert not check({"found": True, "citations": []}, P)[0]


def test_not_found_needs_no_citation():
    assert check({"found": False, "citations": []}, P) == (True, [])
