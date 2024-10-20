"""Abstract class to make authenticated requests."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Self

from podme_api.const import DEFAULT_REQUEST_TIMEOUT

if TYPE_CHECKING:
    from aiohttp import ClientSession

    from podme_api.auth.models import PodMeUserCredentials

_LOGGER = logging.getLogger(__name__)


@dataclass
class PodMeAuthClient(ABC):
    """Abstract base class for making authenticated requests to PodMe API.

    This class provides a framework for handling authentication and making
    requests to the PodMe API. It manages user credentials, access tokens,
    and client sessions.
    """

    user_credentials: PodMeUserCredentials | None = None
    """(PodMeUserCredentials | None): User authentication credentials."""
    session: ClientSession | None = None
    """(ClientSession | None): The :class:`aiohttp.ClientSession` to use for making requests."""
    request_timeout: float = DEFAULT_REQUEST_TIMEOUT
    """Timeout for API requests in seconds."""
    region: str = "NO"
    """Region for authentication"""

    _close_session: bool = False
    """Flag to determine if the session should be closed."""
    _access_token: str | None = None
    """Cached access token for authentication."""

    @abstractmethod
    async def async_get_access_token(self) -> str:
        """Asynchronously retrieve a valid access token.

        Returns:
            str: A valid access token for authentication.

        """
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def get_credentials(self) -> dict | None:
        """Retrieve the current credentials.

        Returns:
            dict | None: A dictionary containing credentials, or None if not set.

        """
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def set_credentials(self, credentials):
        """Set new credentials.

        Args:
            credentials: The new credentials to be set.

        """
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def invalidate_credentials(self):
        """Invalidate the current credentials."""
        raise NotImplementedError  # pragma: no cover

    async def close(self) -> None:
        """Close open client session."""
        if self.session and self._close_session:
            await self.session.close()

    async def __aenter__(self) -> Self:
        """Async enter."""
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        """Async exit."""
        await self.close()
