class CopilotError(Exception):
    status_code = 500
    error_code = "copilot_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ProviderConfigurationError(CopilotError):
    status_code = 503
    error_code = "provider_configuration_error"


class ProviderError(CopilotError):
    status_code = 502
    error_code = "provider_error"


class RetrievalError(CopilotError):
    status_code = 500
    error_code = "retrieval_error"


class UnsupportedDocumentError(CopilotError):
    status_code = 400
    error_code = "unsupported_document"

