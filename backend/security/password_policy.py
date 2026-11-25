"""Rules every new password must meet (create, reset, change, CLI)."""

MIN_LENGTH = 12
MAX_LENGTH = 256


def password_problem(username: str, password: str) -> str | None:
    """Return a user-facing reason the password is not allowed, or None."""
    if len(password) < MIN_LENGTH:
        return f"Password must contain at least {MIN_LENGTH} characters."
    if len(password) > MAX_LENGTH:
        return f"Password must be at most {MAX_LENGTH} characters."
    if not password.strip():
        return "Password must not be only spaces."
    if username.strip().lower() in password.lower():
        return "Password must not contain the username."
    return None
