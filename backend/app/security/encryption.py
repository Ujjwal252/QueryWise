
import base64
import logging
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from config import Config


logger = logging.getLogger(__name__)


class EncryptionError(Exception):
    """Raised when encryption or decryption fails."""


def get_encryption_key():
    """
    Load and validate the AES-256 encryption key.

    Returns:
        bytes: A valid 32-byte encryption key.

    Raises:
        EncryptionError: If the key is missing or invalid.
    """

    encoded_key = Config.DB_ENCRYPTION_KEY

    if not encoded_key:
        raise EncryptionError(
            "Database encryption key is not configured."
        )

    try:
        key = base64.urlsafe_b64decode(encoded_key)

    except Exception as error:
        raise EncryptionError(
            "Database encryption key has an invalid format."
        ) from error

    if len(key) != 32:
        raise EncryptionError(
            "Database encryption key must decode to 32 bytes."
        )

    return key


def encrypt_password(plain_text):
    """
    Encrypt an external database password using AES-256-GCM.

    Returns:
        str: Base64-encoded nonce and ciphertext.
    """

    if not isinstance(plain_text, str) or not plain_text:
        raise ValueError("Password must be a non-empty string.")

    try:
        key = get_encryption_key()

        nonce = os.urandom(12)

        aesgcm = AESGCM(key)

        ciphertext = aesgcm.encrypt(
            nonce,
            plain_text.encode("utf-8"),
            None
        )

        encrypted_data = nonce + ciphertext

        return base64.urlsafe_b64encode(
            encrypted_data
        ).decode("utf-8")

    except EncryptionError:
        raise

    except Exception as error:
        logger.exception("Database password encryption failed.")

        raise EncryptionError(
            "Unable to encrypt database password."
        ) from error


def decrypt_password(encrypted_text):
    """
    Decrypt an AES-256-GCM encrypted database password.

    Returns:
        str: Original database password.

    Raises:
        EncryptionError: If decryption or authentication fails.
    """

    if not isinstance(encrypted_text, str) or not encrypted_text:
        raise ValueError("Encrypted password must be a non-empty string.")

    try:
        key = get_encryption_key()

        encrypted_data = base64.urlsafe_b64decode(encrypted_text)

        if len(encrypted_data) < 12 + 16:
            raise EncryptionError(
                "Encrypted password data is invalid."
            )

        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]

        aesgcm = AESGCM(key)

        plaintext = aesgcm.decrypt(
            nonce,
            ciphertext,
            None
        )

        return plaintext.decode("utf-8")

    except EncryptionError:
        raise

    except (InvalidTag, ValueError) as error:
        logger.warning(
            "Database password decryption failed authentication."
        )

        raise EncryptionError(
            "Unable to decrypt database password. "
            "The key may be incorrect or the data may be corrupted."
        ) from error

    except Exception as error:
        logger.exception("Database password decryption failed.")

        raise EncryptionError(
            "Unable to decrypt database password."
        ) from error
