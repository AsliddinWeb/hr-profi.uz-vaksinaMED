from app.api.ws import origin_allowed


def test_origin_must_match_host():
    assert origin_allowed("https://c1.vaksinahr.uz", "c1.vaksinahr.uz")
    assert origin_allowed("http://localhost:6788", "localhost:6788")
    assert origin_allowed(None, "anything")  # brauzer bo'lmagan mijoz
    assert not origin_allowed("https://evil.example", "c1.vaksinahr.uz")
    assert not origin_allowed("https://c1.vaksinahr.uz.evil.example", "c1.vaksinahr.uz")
