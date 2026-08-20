import hashlib
import hmac

from src.integrations.whatsapp.signature import verify_meta_signature


def test_valid_signature():
    body = b'{"ok":true}'
    secret = "secret"
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_meta_signature(body, "sha256=" + digest, secret)


def test_invalid_signature():
    assert not verify_meta_signature(b"x", "sha256=bad", "secret")
