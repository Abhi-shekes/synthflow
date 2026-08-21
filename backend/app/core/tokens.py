import secrets


def generate_token() -> str:
    """An unguessable capability token for public, unauthenticated URLs
    (RestOutput, WebSocketStream) — possessing it is the access control,
    the same trust model as a webhook URL."""
    return secrets.token_urlsafe(24)
