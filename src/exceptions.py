"""
Custom Exceptions für CatchSnapWeb Traffic Recorder
"""

from typing import Optional


class CatchSnapException(Exception):
    """Base exception for all CatchSnap errors"""
    def __init__(self, message: str, details: Optional[dict] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message


class BlobDownloadError(CatchSnapException):
    """Error downloading blob URLs"""
    pass


class BlobValidationError(CatchSnapException):
    """Error validating blob data"""
    pass


class BrowserLaunchError(CatchSnapException):
    """Error launching browser"""
    pass


class ConfigurationError(CatchSnapException):
    """Configuration error"""
    pass


class StorageError(CatchSnapException):
    """Error saving data"""
    pass


class DiskSpaceError(StorageError):
    """Insufficient disk space available"""
    pass


class SessionError(CatchSnapException):
    """Error in session management"""
    pass


class NetworkRecordingError(CatchSnapException):
    """Error in network recording"""
    pass


class ExportError(CatchSnapException):
    """Error exporting data"""
    pass
