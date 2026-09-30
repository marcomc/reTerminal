"""Fixed public errors: upstream bodies, URLs and exception text stay private."""

MESSAGES = {
    "validation": "Check the supplied settings and resource selections.",
    "key_missing": "Connect SenseCraft with an API key first.",
    "key_invalid": "The SenseCraft API key is invalid or no longer authorized.",
    "environment_override": "An explicit SENSECRAFT_API_KEY environment override is active. Restart without it before pasting a different key.",
    "google_missing": "Connect Google Calendar through SenseCraft first.",
    "google_expired": "The Google connection expired or was revoked. Reconnect it.",
    "network": "The remote service could not be reached. Try again.",
    "upstream": "The remote service refused this operation.",
    "protocol": "The remote service returned an unexpected response.",
    "uncertain_upload": "An upload may have succeeded, but its URL was not received. Automatic retry is paused to avoid duplicate uploads.",
    "uncertain_create": "Page creation may have succeeded. The saved journal will reconcile it before any retry.",
    "readback": "The saved page or device assignment could not be verified. Retry to reconcile the saved state.",
    "busy": "A preview or publication is running. Wait for it to finish.",
    "stopped": "The configurator is shutting down. Durable progress was preserved for retry.",
    "forbidden": "This request is not authorized for the local configurator.",
    "not_found": "The requested local resource was not found.",
    "internal": "The operation could not be completed. Local recovery state was preserved.",
}


class AppError(Exception):
    def __init__(self, code, status=400, retryable=False):
        self.code = code
        self.status = status
        self.retryable = retryable
        super().__init__(MESSAGES[code])

    def public(self):
        return {
            "code": self.code,
            "message": MESSAGES[self.code],
            "retryable": self.retryable,
        }


def safe_error(exc):
    return exc if isinstance(exc, AppError) else AppError("internal", 500)
