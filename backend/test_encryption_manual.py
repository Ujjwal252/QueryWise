
from app.security.encryption import (
    encrypt_password,
    decrypt_password
)


def main():
    test_password = "QueryWise_Test_DB_Password_123!"

    encrypted = encrypt_password(test_password)
    decrypted = decrypt_password(encrypted)

    print("Encryption successful:", encrypted != test_password)
    print("Decryption successful:", decrypted == test_password)


if __name__ == "__main__":
    main()
