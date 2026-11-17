
import base64

import pytest

from app.security.encryption import (
    encrypt_password,
    decrypt_password,
    get_encryption_key,
    EncryptionError
)


TEST_PASSWORD = "QueryWise_Test_DB_Password_123!"


def test_encrypt_and_decrypt_password():
    """Verify that encryption and decryption preserve the password."""

    encrypted = encrypt_password(TEST_PASSWORD)

    assert encrypted != TEST_PASSWORD
    assert decrypt_password(encrypted) == TEST_PASSWORD


def test_same_password_produces_different_ciphertext():
    """Verify that every encryption uses a fresh random nonce."""

    encrypted_first = encrypt_password(TEST_PASSWORD)
    encrypted_second = encrypt_password(TEST_PASSWORD)

    assert encrypted_first != encrypted_second

    assert decrypt_password(encrypted_first) == TEST_PASSWORD
    assert decrypt_password(encrypted_second) == TEST_PASSWORD


def test_tampered_ciphertext_is_rejected():
    """Verify that modified encrypted data fails authentication."""

    encrypted = encrypt_password(TEST_PASSWORD)

    encrypted_bytes = bytearray(
        base64.urlsafe_b64decode(encrypted)
    )

    encrypted_bytes[-1] ^= 1

    tampered_data = base64.urlsafe_b64encode(
        encrypted_bytes
    ).decode("utf-8")

    with pytest.raises(EncryptionError):
        decrypt_password(tampered_data)


def test_invalid_encryption_key_is_rejected(monkeypatch):
    """Verify that an incorrect key cannot decrypt existing data."""

    encrypted = encrypt_password(TEST_PASSWORD)

    monkeypatch.setattr(
        "app.security.encryption.Config.DB_ENCRYPTION_KEY",
        base64.urlsafe_b64encode(b"A" * 32).decode("utf-8")
    )

    with pytest.raises(EncryptionError):
        decrypt_password(encrypted)


def test_missing_encryption_key_is_rejected(monkeypatch):
    """Verify that encryption fails safely when the key is missing."""

    monkeypatch.setattr(
        "app.security.encryption.Config.DB_ENCRYPTION_KEY",
        None
    )

    with pytest.raises(EncryptionError):
        get_encryption_key()


def test_invalid_key_length_is_rejected(monkeypatch):
    """Verify that keys other than 32 bytes are rejected."""

    invalid_key = base64.urlsafe_b64encode(
        b"short-key"
    ).decode("utf-8")

    monkeypatch.setattr(
        "app.security.encryption.Config.DB_ENCRYPTION_KEY",
        invalid_key
    )

    with pytest.raises(EncryptionError):
        get_encryption_key()


@pytest.mark.parametrize("invalid_password", ["", None, 123])
def test_invalid_password_input_is_rejected(invalid_password):
    """Verify that invalid plaintext inputs are rejected."""

    with pytest.raises(ValueError):
        encrypt_password(invalid_password)


@pytest.mark.parametrize("invalid_data", ["", None, 123])
def test_invalid_encrypted_input_is_rejected(invalid_data):
    """Verify that invalid encrypted inputs are rejected."""

    with pytest.raises(ValueError):
        decrypt_password(invalid_data)
