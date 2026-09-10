from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

PASSWORD_HASHER = PasswordHash.recommended()
_DUMMY_PASSWORD_HASH = PASSWORD_HASHER.hash("zsme-invalid-login-dummy-password")


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("password must be at least 12 characters")
    if len(password) > 256:
        raise ValueError("password must be at most 256 characters")
    return PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(password, password_hash)
    except (TypeError, ValueError, UnknownHashError):
        # Corrupt or legacy hashes must fail closed without turning a login
        # attempt into a 500 response.
        return False


def dummy_password_hash() -> str:
    """Return a fixed-cost hash for timing-safe nonexistent-user logins."""
    return _DUMMY_PASSWORD_HASH
