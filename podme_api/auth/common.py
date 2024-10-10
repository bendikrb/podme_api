"""Abstract class to make authenticated requests."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Self

from podme_api.const import TIMEOUT

if TYPE_CHECKING:
    from aiohttp import ClientSession

    from podme_api.auth.models import PodMeUserCredentials

_LOGGER = logging.getLogger(__name__)


@dataclass
class PodMeAuthClient(ABC):
    """Abstract class to make authenticated requests."""

    user_credentials: PodMeUserCredentials | None = None
    session: ClientSession | None = None
    request_timeout: int = TIMEOUT

    _close_session: bool = False
    _access_token: str | None = None

    @abstractmethod
    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        raise NotImplementedError

    @abstractmethod
    def get_credentials(self) -> dict | None:
        """Return credentials as dict."""
        raise NotImplementedError

    @abstractmethod
    def set_credentials(self, credentials):
        """Return credentials as dict."""
        raise NotImplementedError

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
