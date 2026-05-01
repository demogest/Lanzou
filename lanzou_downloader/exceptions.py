class LanzouError(Exception):
    """Base error for recoverable downloader failures."""


class NetworkError(LanzouError):
    """Raised when an HTTP request fails."""


class ParseError(LanzouError):
    """Raised when Lanzou page markup no longer matches expected patterns."""


class PasswordError(LanzouError):
    """Raised when a password is missing or rejected."""


class UnsupportedLinkError(LanzouError):
    """Raised for share link shapes the app does not support yet."""


class DownloadError(LanzouError):
    """Raised when writing a downloaded file fails."""
