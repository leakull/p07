from datetime import timedelta

from jose import jwt

from app.database import settings
from app.routers.auth import create_access_token, get_password_hash, verify_password


def test_password_hash_and_verify_success():
    password = "StrongPass123!"
    hashed = get_password_hash(password)

    assert hashed != password
    assert verify_password(password, hashed) is True


def test_password_verify_fails_for_wrong_password():
    hashed = get_password_hash("correct-password")

    assert verify_password("wrong-password", hashed) is False


def test_create_access_token_contains_subject_and_role():
    token = create_access_token(
        {"sub": "user-123", "role": "admin"},
        expires_delta=timedelta(minutes=5),
    )
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    assert payload["sub"] == "user-123"
    assert payload["role"] == "admin"
    assert "exp" in payload
