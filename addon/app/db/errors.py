"""Persistence-layer exceptions."""


class NotFoundError(LookupError):
    """Raised when a requested row does not exist."""


class DuplicateNameError(ValueError):
    """Raised when a case-insensitive unique name is already taken."""


class SchemaVersionError(RuntimeError):
    """Raised when the database was written by a newer add-on version."""
