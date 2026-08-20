from src.integrations.whatsapp.client import split_whatsapp_text


def test_split_preserves_content():
    original = "a" * 8001
    chunks = split_whatsapp_text(original, limit=3500)
    assert all(len(chunk) <= 3500 for chunk in chunks)
    assert "".join(chunks) == original
