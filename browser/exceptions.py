"""
Custom exceptions for the image browser application.
"""


class PathNotFoundError(Exception):
    """Raised when a requested path does not exist."""
    pass


class InvalidRequestError(Exception):
    """Raised when request data is invalid."""
    pass


class FileOperationError(Exception):
    """Raised when file operations fail."""
    pass

