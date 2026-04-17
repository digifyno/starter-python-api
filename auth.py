"""Auth helper functions for password hashing and JWT token management."""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    encoded = password.encode()
    if len(encoded) > 72:
        raise ValueError("Password must not exceed 72 bytes (bcrypt limit)")
    return bcrypt.hashpw(encoded, bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches the bcrypt hashed password."""
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


def create_access_token(
    data: dict, secret_key: str, expires_in: timedelta = timedelta(hours=1)
) -> str:
    """Encode a JWT token with an expiry claim."""
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_in
    return jwt.encode(payload, secret_key, algorithm="HS256")


def decode_access_token(token: str, secret_key: str) -> dict:
    """Decode and verify a JWT token.

    Raises:
        jwt.ExpiredSignatureError: if the token has expired.
        jwt.exceptions.InvalidTokenError: if the token is invalid.
    """
    return jwt.decode(token, secret_key, algorithms=["HS256"])
