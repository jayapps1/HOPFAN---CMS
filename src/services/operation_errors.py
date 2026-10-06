"""Typed operation failures shared by desktop services and online adapters."""
class OperationConflict(Exception):
    """The loaded version or a uniqueness constraint no longer matches."""

class OperationNotFound(Exception):
    """An authorized resource is unavailable."""
