from hashlib import sha256
import re


def stable_hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()[:24]


def normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    return digits or None
