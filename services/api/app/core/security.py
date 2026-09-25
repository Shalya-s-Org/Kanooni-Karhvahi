import secrets
from typing import Dict


def generate_secure_token(nbytes: int = 32) -> str:
    """
    Generates a cryptographically secure random token.
    """
    return secrets.token_urlsafe(nbytes)


def get_security_headers() -> Dict[str, str]:
    """
    Returns standard HTTP security response headers.
    """
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'",
    }
