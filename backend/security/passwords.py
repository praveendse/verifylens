"""Password hashing with Argon2 using pwdlib's recommended configuration."""

from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()


def hash_password(plain_password: str) -> str:
    return _password_hash.hash(plain_password)


def verify_password(plain_password: str, stored_hash: str) -> bool:
    return _password_hash.verify(plain_password, stored_hash)
