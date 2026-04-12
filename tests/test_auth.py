"""Tests for auth helper functions: bcrypt password hashing and JWT token management."""

from datetime import timedelta

import bcrypt
import jwt
import pytest
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from auth import create_access_token, decode_access_token, hash_password, verify_password

TEST_SECRET = "test-secret-key-32-chars-minimum!"


# ---------------------------------------------------------------------------
# hash_password / verify_password
# ---------------------------------------------------------------------------

def test_hash_password_returns_bcrypt_hash():
    hashed = hash_password("mysecret")
    assert hashed.startswith("$2b$"), "bcrypt hashes must start with $2b$"


def test_hash_password_not_plaintext():
    password = "mysecret"
    hashed = hash_password(password)
    assert hashed != password


def test_hash_password_is_unique_per_call():
    """Two hashes of the same password must differ due to random salt."""
    password = "samepassword"
    hash1 = hash_password(password)
    hash2 = hash_password(password)
    assert hash1 != hash2, "bcrypt must produce a unique hash on each call (random salt)"


def test_verify_password_correct():
    password = "correcthorsebatterystaple"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("correctpassword")
    assert verify_password("wrongpassword", hashed) is False


def test_verify_password_uses_fast_rounds():
    """Ensure tests don't accidentally use slow rounds — bcrypt with rounds=4 is fast enough."""
    fast_hash = bcrypt.hashpw(b"pass", bcrypt.gensalt(rounds=4)).decode()
    assert verify_password("pass", fast_hash) is True


# ---------------------------------------------------------------------------
# create_access_token / decode_access_token
# ---------------------------------------------------------------------------

def test_token_round_trip():
    data = {"sub": "user-42", "role": "admin"}
    token = create_access_token(data, TEST_SECRET)
    decoded = decode_access_token(token, TEST_SECRET)
    assert decoded["sub"] == "user-42"
    assert decoded["role"] == "admin"


def test_token_contains_exp_claim():
    token = create_access_token({"sub": "user-1"}, TEST_SECRET)
    decoded = decode_access_token(token, TEST_SECRET)
    assert "exp" in decoded


def test_expired_token_raises():
    token = create_access_token({"sub": "user-1"}, TEST_SECRET, expires_in=timedelta(seconds=-1))
    with pytest.raises(ExpiredSignatureError):
        decode_access_token(token, TEST_SECRET)


def test_wrong_secret_raises():
    token = create_access_token({"sub": "user-1"}, TEST_SECRET)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, "wrong-secret-key-32-chars-minimum!")


def test_tampered_token_raises():
    token = create_access_token({"sub": "user-1"}, TEST_SECRET)
    # Flip one character in the signature (last segment)
    parts = token.split(".")
    parts[-1] = parts[-1][:-1] + ("A" if parts[-1][-1] != "A" else "B")
    tampered = ".".join(parts)
    with pytest.raises(InvalidTokenError):
        decode_access_token(tampered, TEST_SECRET)


def test_decode_garbage_token_raises_invalid_token_error():
    """Completely malformed token string raises InvalidTokenError."""
    with pytest.raises(InvalidTokenError):
        decode_access_token("not.a.jwt", TEST_SECRET)
