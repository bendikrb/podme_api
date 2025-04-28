"""Abstract class to make authenticated requests."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import logging
import os
import sys
from typing import TYPE_CHECKING, Self

from podme_api.const import DEFAULT_REQUEST_TIMEOUT

if TYPE_CHECKING:
    from aiohttp import ClientResponse, ClientSession
    from yarl import URL

    from podme_api.auth.models import PodMeUserCredentials, PyTestHttpFixture

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

    _close_session: bool = False
    """Flag to determine if the session should be closed."""
    _access_token: str | None = None
    """Cached access token for authentication."""
    _pytest_session: str | None = None
    """Name of the current pytest session."""
    _pytest_sessions: dict[str, list[PyTestHttpFixture]] = field(default_factory=dict)
    """Store responses for pytest fixtures."""

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

    @property
    def credentials_filename(self):
        """Get the filename for storing credentials."""
        return "credentials.json"

    def start_pytest_recording(self, name: str):
        """Start recording responses for pytest fixtures."""
        if os.getenv("UPDATE_FIXTURES") is None or "pytest" not in sys.modules:
            return
        self._pytest_session = name
        self._pytest_sessions[name] = []

    def stop_pytest_recording(self):
        """Stop recording responses for pytest fixtures."""
        self._pytest_session = None

    def get_pytest_recordings(self):
        """Get the recorded responses for pytest fixtures."""
        return self._pytest_sessions

    async def _record_response(
        self,
        url: URL,
        method: str,
        response: ClientResponse,
    ):
        """Record a response for a fixture."""
        if self._pytest_session is None:
            return
        fixture_name = "-".join(url.path.lstrip("/").rstrip("/").split("/"))
        fixture_no = len(self._pytest_sessions[self._pytest_session]) + 1
        self._pytest_sessions[self._pytest_session].append(
            {
                "no": fixture_no,
                "status": response.status,
                "headers": dict(response.headers),
                "body": await response.text(),
                "method": method,
                "url": str(url),
                "fixture_name": f"{self._pytest_session}_{fixture_no}_{fixture_name}",
            }
        )

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
