import re
import hashlib
import hmac

from cryptography.fernet import Fernet

from app.config import settings


fernet = Fernet(settings.factory_secret_key.encode())

SECRET_PATTERNS = [
    re.compile(r"(sk-[A-Za-z0-9_\-]{16,})"),
    re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)([A-Za-z0-9_\-]{12,})"),
    re.compile(r"(?i)(authorization:\s*bearer\s+)([A-Za-z0-9_\-.]+)"),
]


def encrypt_secret(value: str) -> str:
    return fernet.encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    return fernet.decrypt(value.encode()).decode()


def secret_fingerprint(value: str) -> str:
    normalized = value.strip()
    digest = hmac.new(settings.factory_secret_key.encode(), normalized.encode(), hashlib.sha256)
    return digest.hexdigest()


def key_hint(value: str) -> str:
    if len(value) <= 8:
        return "****"
    return f"{value[:3]}...{value[-4:]}"


def redact(value: str | None) -> str | None:
    if not value:
        return value
    redacted = value
    for pattern in SECRET_PATTERNS:
        if pattern.groups >= 2:
            redacted = pattern.sub(lambda match: f"{match.group(1)}[REDACTED]", redacted)
        else:
            redacted = pattern.sub("[REDACTED]", redacted)
    return redacted
