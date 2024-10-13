from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from http import HTTPStatus
import json
import logging
import socket
from typing import TYPE_CHECKING
from urllib.parse import unquote

from aiohttp import ClientError, ClientResponse, ClientResponseError, ClientSession
from aiohttp.hdrs import METH_GET, METH_POST
from yarl import URL

from podme_api.auth.common import PodMeAuthClient
from podme_api.auth.models import SchibstedCredentials
from podme_api.auth.utils import get_now_iso, get_uuid, parse_schibsted_auth_html
from podme_api.const import (
    PODME_AUTH_BASE_URL,
    PODME_AUTH_RETURN_URL,
    PODME_AUTH_USER_AGENT,
    PODME_BASE_URL,
)
from podme_api.exceptions import (
    PodMeApiAuthenticationError,
    PodMeApiConnectionError,
    PodMeApiConnectionTimeoutError,
    PodMeApiError,
)

if TYPE_CHECKING:
    from podme_api.auth.models import PodMeUserCredentials

_LOGGER = logging.getLogger(__name__)


CLIENT_ID = "66fd26cdae6bde57ef206b35"


@dataclass
class PodMeDefaultAuthClient(PodMeAuthClient):
    """Default authentication client for PodMe.

    This class handles authentication using Schibsted credentials for the PodMe service.
    """

    user_agent = PODME_AUTH_USER_AGENT
    """User agent string for API requests."""

    device_data = {
        "platform": "Ubuntu",
        "userAgent": "Firefox",
        "userAgentVersion": "131.0",
        "hasLiedOs": "0",
        "hasLiedBrowser": "0",
        "fonts": [
            "Arial",
            "Bitstream Vera Sans Mono",
            "Bookman Old Style",
            "Century Schoolbook",
            "Courier",
            "Courier New",
            "Helvetica",
            "MS Gothic",
            "MS PGothic",
            "Palatino",
            "Palatino Linotype",
            "Times",
            "Times New Roman",
        ],
        "plugins": [
            "PDF Viewer::Portable Document Format::application/pdf~pdf,text/pdf~pdf",
            "Chrome PDF Viewer::Portable Document Format::application/pdf~pdf,text/pdf~pdf",
            "Chromium PDF Viewer::Portable Document Format::application/pdf~pdf,text/pdf~pdf",
            "Microsoft Edge PDF Viewer::Portable Document Format::application/pdf~pdf,text/pdf~pdf",
            "WebKit built-in PDF::Portable Document Format::application/pdf~pdf,text/pdf~pdf",
        ],
    }
    """Device information for authentication."""

    credentials: SchibstedCredentials | None = None
    """(SchibstedCredentials | None): Authentication credentials."""

    _credentials: SchibstedCredentials | None = field(default=None, init=False)
    _close_session: bool = False

    def __post_init__(self):
        """Initialize the client after dataclass initialization."""
        if self.credentials is not None:
            self.set_credentials(self.credentials)

    @property
    def request_header(self) -> dict[str, str]:
        """Generate a header for HTTP requests to the server."""
        return {
            "Accept": "text/html",
            "User-Agent": self.user_agent,
            "Referer": PODME_BASE_URL,
        }

    async def _request(
        self,
        uri: str,
        method: str = METH_GET,
        base_url: str | None = None,
        **kwargs,
    ) -> ClientResponse:
        """Make an API request to the PodMe server.

        Args:
            uri (str): The URI for the API endpoint.
            method (str, optional): The HTTP method to use. Defaults to METH_GET.
            base_url (str | None, optional): The base URL for the request. Defaults to None.
            **kwargs: Additional keyword arguments for the request. Common kwargs include:
                - params (dict): Query parameters for the request.
                - headers (dict): Additional headers to send with the request.
                - data (dict): Form data to send in the request body.
                - json (dict): JSON data to send in the request body.

        Returns:
            ClientResponse: The response from the API request.

        Raises:
            PodMeApiConnectionTimeoutError: If a timeout occurs during the request.
            PodMeApiError: If there's a bad request syntax or unsupported method.
            PodMeApiConnectionError: For other API communication errors.

        """
        if base_url is None:
            base_url = PODME_AUTH_BASE_URL
        url = URL(base_url).join(URL(uri))
        headers = {
            **self.request_header,
            **kwargs.get("headers", {}),
        }
        kwargs.update({"headers": headers})

        if self.session is None or self.session.closed:
            self.session = ClientSession()
            _LOGGER.debug("New session created.")
            self._close_session = True

        _LOGGER.debug(
            "Executing %s API request to %s.",
            method,
            url.with_query(kwargs.get("params")),
        )

        try:
            async with asyncio.timeout(self.request_timeout):
                response = await self.session.request(
                    method,
                    url,
                    **kwargs,
                )
                response.raise_for_status()
        except asyncio.TimeoutError as exception:
            raise PodMeApiConnectionTimeoutError(
                "Timeout occurred while trying to authorize with PodMe"
            ) from exception
        except (
            ClientError,
            ClientResponseError,
            socket.gaierror,
        ) as exception:
            if hasattr(exception, "status") and exception.status == HTTPStatus.BAD_REQUEST:
                raise PodMeApiError("Bad request syntax or unsupported method") from exception
            msg = f"Error occurred while communicating with PodMe/Schibsted API: {exception}"
            raise PodMeApiConnectionError(msg) from exception

        return response

    async def async_get_access_token(self) -> str:
        """Get a valid access token.

        Returns:
            str: The access token.

        Raises:
            PodMeApiAuthenticationError: If no user credentials are provided.

        """
        if not self._credentials:
            if not self.user_credentials:
                raise PodMeApiAuthenticationError("No user credentials provided")
            credentials = await self.authorize(self.user_credentials)
        elif self._credentials.is_expired():
            credentials = await self.refresh_token()
        else:
            credentials = self._credentials
        return credentials.access_token

    async def authorize(self, user_credentials: PodMeUserCredentials) -> SchibstedCredentials:
        """Authorize the user and obtain credentials.

        The obtained credentials is internally stored in the client.

        Args:
            user_credentials (PodMeUserCredentials): The user's credentials.

        Raises:
            PodMeApiConnectionTimeoutError: If a timeout occurs during a request.
            PodMeApiError: If there's a bad request syntax or unsupported method.
            PodMeApiConnectionError: For other API communication errors.

        """
        # Authorize
        response = await self._request(
            "oauth/authorize",
            params={
                "client_id": CLIENT_ID,
                "redirect_uri": "https://podme.com/auth/handleSchibstedLogin",
                "response_type": "code",
                "scope": "openid email",
                "state": json.dumps(
                    {
                        "returnUrl": PODME_AUTH_RETURN_URL,
                        "uuid": get_uuid(),
                        "schibstedFlowInitiatedDate": get_now_iso(),
                    }
                ),
                "prompt": "select_account",
            },
        )
        text = await response.text()
        bff_data = parse_schibsted_auth_html(text)
        _LOGGER.debug(f"BFF data: {bff_data}")
        csrf_token = bff_data.csrf_token

        # Login: step 1/2
        response = await self._request(
            "authn/api/identity/email-status",
            method=METH_POST,
            params={"client_id": CLIENT_ID},
            headers={
                "X-CSRF-Token": csrf_token,
                "Accept": "application/json",
            },
            data={
                "email": user_credentials.email,
                "deviceData": json.dumps(self.device_data),
            },
        )
        email_status = await response.json()
        _LOGGER.debug(f"Email status: {email_status}")

        # Login: step 2/2
        response = await self._request(
            "authn/api/identity/login/",
            method=METH_POST,
            params={"client_id": CLIENT_ID},
            headers={
                "X-CSRF-Token": csrf_token,
                "Accept": "application/json",
            },
            data={
                "username": user_credentials.email,
                "password": user_credentials.password,
                "remember": "true",
                "deviceData": json.dumps(self.device_data),
            },
        )
        login_response = await response.json()
        _LOGGER.debug(f"Login response: {login_response}")

        # Finalize login
        response = await self._request(
            "authn/identity/finish/",
            method=METH_POST,
            params={"client_id": CLIENT_ID},
            data={
                "deviceData": json.dumps(self.device_data),
                "remember": "true",
                "_csrf": csrf_token,
                "redirectToAccountPage": "",
            },
        )
        final_location = response.history[-1].headers.get("Location")
        jwt_cookie = response.history[-1].cookies.get("jwt-cred").value
        jwt_cred = unquote(jwt_cookie)
        self.set_credentials(jwt_cred)

        _LOGGER.debug(f"Login successful: (final location: {final_location})")

        await self.close()

        return self._credentials

    async def refresh_token(self, credentials: SchibstedCredentials | None = None):
        """Refresh the access token.

        The obtained credentials is internally stored in the client (:attr:`_credentials`).

        Args:
            credentials (SchibstedCredentials, optional): The credentials to refresh. Defaults to :attr:`_credentials`.

        Returns:
            SchibstedCredentials: The refreshed credentials.

        """
        if credentials is None:
            credentials = self._credentials

        response = await self._request(
            "auth/refreshSchibstedSession",
            base_url=PODME_BASE_URL,
            json={
                "code": credentials.refresh_token,
                "state": get_uuid(),
            },
        )
        credentials = await response.json()
        self.set_credentials(credentials)
        _LOGGER.debug(f"Refreshed credentials: {self.get_credentials()}")

        await self.close()

        return self._credentials

    def get_credentials(self) -> dict | None:
        """Get the current credentials as a dictionary, or None if not set."""
        if self._credentials is not None:
            return self._credentials.to_dict()
        return None

    def set_credentials(self, credentials: SchibstedCredentials | dict | str):
        """Set the credentials.

        Args:
            credentials (SchibstedCredentials | dict | str): The credentials to set.

        """
        if isinstance(credentials, SchibstedCredentials):
            self._credentials = credentials
        elif isinstance(credentials, dict):
            self._credentials = SchibstedCredentials.from_dict(credentials)
        else:
            self._credentials = SchibstedCredentials.from_json(credentials)
