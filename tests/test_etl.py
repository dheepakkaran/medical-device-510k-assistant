from etl.devices import transform


def test_transform_cleans_dedupes_and_drops():
    raw = [
        {"k_number": "K1", "device_name": "  Pulse   Oximeter ", "product_code": "dqa", "decision_date": "2024-01-05"},
        {"k_number": "K1", "device_name": "dup", "product_code": "DQA", "decision_date": "2024-01-05"},
        {"k_number": None, "device_name": "no k", "product_code": "DQA"},
        {"k_number": "K2", "device_name": "", "product_code": "DQA"},
        {"k_number": "K3", "device_name": "Cuff", "product_code": "DXN", "decision_date": "not a date"},
    ]
    df = transform(raw)
    assert list(df["k_number"]) == ["K1", "K3"]
    assert df.iloc[0]["device_name"] == "Pulse Oximeter"
    assert df.iloc[0]["product_code"] == "DQA"
    assert str(df.iloc[0]["decision_date"]) == "2024-01-05"
    assert df.iloc[1]["decision_date"] is None or str(df.iloc[1]["decision_date"]) in ("NaT", "None")
