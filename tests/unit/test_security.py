"""Unit tests for security, password hashing, and JWT tokens."""
import pytest
from backend.app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token
)


def test_password_hashing():
    pwd = "EnterpriseSecurePass123!"
    hashed = hash_password(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPass", hashed) is False


def test_jwt_access_and_refresh_tokens():
    user_id = "test-user-123"
    claims = {"org_id": "test-org-456", "role": "admin"}

    access_token = create_access_token(user_id, claims=claims)
    decoded_access = decode_token(access_token)
    assert decoded_access is not None
    assert decoded_access["sub"] == user_id
    assert decoded_access["org_id"] == "test-org-456"
    assert decoded_access["type"] == "access"

    refresh_token = create_refresh_token(user_id)
    decoded_refresh = decode_token(refresh_token)
    assert decoded_refresh is not None
    assert decoded_refresh["sub"] == user_id
    assert decoded_refresh["type"] == "refresh"
