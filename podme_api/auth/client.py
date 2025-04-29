from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
from http import HTTPStatus
import json
import logging
import os
import secrets
import socket
from typing import TYPE_CHECKING

from aiohttp import ClientError, ClientResponse, ClientResponseError, ClientSession
from aiohttp.hdrs import METH_GET, METH_POST
import pkce
from yarl import URL

from podme_api.auth.common import PodMeAuthClient
from podme_api.auth.models import SchibstedCredentials
from podme_api.const import (
    PODME_AUTH_BASE_URL,
    PODME_AUTH_CLIENT_ID,
    PODME_AUTH_USER_AGENT,
    PODME_BASE_URL,
)
from podme_api.exceptions import (
    PodMeApiAuthenticationError,
    PodMeApiConnectionError,
    PodMeApiConnectionTimeoutError,
    PodMeApiError,
)
from podme_api.models import PodMeRegion

if TYPE_CHECKING:
    from podme_api.auth.models import PodMeUserCredentials

_LOGGER = logging.getLogger(__name__)


@dataclass
class PodMeDefaultAuthClient(PodMeAuthClient):
    """Default authentication client for PodMe.

    This class handles authentication using Schibsted credentials for the PodMe service.
    """

    user_agent = PODME_AUTH_USER_AGENT
    """User agent string for API requests."""

    device_data = {
        "platform": "Android",
        "userAgent": "Chrome",
        "userAgentVersion": "128.0.0.0",
        "hasLiedOs": "0",
        "hasLiedBrowser": "0",
        "fonts": [
            "Arial",
            "Courier",
            "Courier New",
            "Georgia",
            "Helvetica",
            "Monaco",
            "Palatino",
            "Tahoma",
            "Times",
            "Times New Roman",
            "Verdana",
        ],
        "plugins": [],
    }
    """Device information for authentication."""

    credentials: SchibstedCredentials | None = None
    """(SchibstedCredentials | None): Authentication credentials."""

    region = PodMeRegion.NO
    """(PodMeRegion): The region setting for the client."""

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

    @property
    def client_id(self) -> str:
        return PODME_AUTH_CLIENT_ID.get(self.region)

    @property
    def base_url(self) -> URL:
        return URL(PODME_AUTH_BASE_URL.get(self.region))

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
            base_url = self.base_url
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
                await self._record_response(url.with_query(kwargs.get("params")), method, response)
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
        self.start_pytest_recording("authorize")
        code_verifier, code_challenge = pkce.generate_pkce_pair()
        response = await self._request(
            "oauth/authorize",
            params={
                "client_id": self.client_id,
                "redirect_uri": f"pme.podme.{self.client_id}:/login",
                "response_type": "code",
                "scope": "openid offline_access",
                "state": hashlib.sha256(os.urandom(1024)).hexdigest(),
                "nonce": secrets.token_urlsafe(),
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
                "prompt": "select_account",
            },
            allow_redirects=False,
        )
        # Login: step 1/3
        await self._request("", base_url=response.headers.get("Location"))
        # Login: step 2/3
        response = await self._request(
            "authn/api/settings/csrf",
            params={"client_id": self.client_id},
        )
        csrf_token = (await response.json())["data"]["attributes"]["csrfToken"]

        # Login: step 3/3
        response = await self._request(
            "authn/api/identity/login/",
            method=METH_POST,
            params={"client_id": self.client_id},
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
            params={"client_id": self.client_id},
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "deviceData": json.dumps(self.device_data),
                "remember": "true",
                "_csrf": csrf_token,
                "redirectToAccountPage": "",
            },
            allow_redirects=False,
        )

        # Follow redirect manually
        response = await self._request("", base_url=response.headers.get("Location"), allow_redirects=False)
        code = URL(response.headers.get("Location")).query.get("code")

        # Request tokens with authorization code
        response = await self._request(
            "oauth/token",
            method=METH_POST,
            headers={
                "X-OIDC": "v1",
                "X-Region": self.region.name,
            },
            data={
                "client_id": self.client_id,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": f"pme.podme.{self.client_id}:/login",
                "code_verifier": code_verifier,
            },
            allow_redirects=False,
        )
        self.stop_pytest_recording()

        jwt_cred = await response.json()
        jwt_cred["expiration_time"] = int(datetime.now(tz=UTC).timestamp() + jwt_cred["expires_in"])
        self.set_credentials(jwt_cred)

        _LOGGER.debug("Login successful")

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

        self.start_pytest_recording("refresh_token")
        response = await self._request(
            "oauth/token",
            method=METH_POST,
            headers={
                "Host": self.base_url.host,
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "AccountSDKAndroidWeb/6.4.0 (Linux; Android 15; API 35; Google; sdk_gphone64_arm64)",
                "X-OIDC": "v1",
                "X-Region": self.region.name,
            },
            data={
                "client_id": self.client_id,
                "grant_type": "refresh_token",
                "refresh_token": credentials.refresh_token,
            },
            allow_redirects=False,
        )
        self.stop_pytest_recording()
        refreshed_credentials = await response.json()
        refreshed_credentials["expiration_time"] = int(
            datetime.now(tz=UTC).timestamp() + refreshed_credentials["expires_in"]
        )
        self.set_credentials(SchibstedCredentials.from_dict({
            **credentials.to_dict(),
            **refreshed_credentials,
        }))

        _LOGGER.debug("Refresh token successful")

        await self.close()
        return self._credentials

    def get_credentials(self) -> dict | None:
        """Get the current credentials as a dictionary, or None if not set."""
        if self._credentials is not None:
            return self._credentials.to_dict()
        return None  # pragma: no cover

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

    def invalidate_credentials(self):
        """Invalidate the current credentials."""
        self._credentials = None
