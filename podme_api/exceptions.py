"""podme_api exceptions."""


class PodMeApiError(Exception):
    """Generic PodMe exception."""


class PodMeApiConnectionError(PodMeApiError):
    """PodMe connection exception."""


class PodMeApiConnectionTimeoutError(PodMeApiConnectionError):
    """PodMe connection timeout exception."""


class PodMeApiRateLimitError(PodMeApiConnectionError):
    """PodMe Rate Limit exception."""


class PodMeApiAuthenticationError(PodMeApiError):
    """PodMe authentication exception."""
