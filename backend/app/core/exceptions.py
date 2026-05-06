from typing import Any


class AppException(Exception):
    status_code = 500
    code = "APPLICATION_ERROR"
    default_message = "Application error."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: Any | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.details = details
        super().__init__(self.message)


class ConfigurationError(AppException):
    status_code = 500
    code = "CONFIGURATION_ERROR"
    default_message = "Application configuration is invalid."
