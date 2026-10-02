class OpenDotaError(Exception):
    """Base class. Messages never contain URLs, so the API key cannot leak through them."""


class OpenDotaNotFound(OpenDotaError):
    """The API answered 404 (unknown player or match)."""


class OpenDotaUnavailable(OpenDotaError):
    """The API is down, rate limiting us or timing out, and no cached copy exists."""
