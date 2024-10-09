from __future__ import annotations

import asyncio
from dataclasses import dataclass
from http import HTTPStatus
import json
import logging
import socket
from typing import TYPE_CHECKING
from urllib.parse import unquote

from aiohttp import ClientError, ClientResponseError, ClientSession
from aiohttp.hdrs import METH_GET, METH_POST
import async_timeout
from yarl import URL

from podme_api.auth.common import PodMeAuthClient
from podme_api.auth.models import SchibstedCredentials
from podme_api.auth.utils import get_now_iso, get_uuid, parse_schibsted_auth_html
from podme_api.exceptions import (
    PodMeApiAuthenticationError,
    PodMeApiConnectionError,
    PodMeApiConnectionTimeoutError,
    PodMeApiError,
)

if TYPE_CHECKING:
    from auth.models import PodMeUserCredentials

_LOGGER = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0"
CLIENT_ID = "66fd26cdae6bde57ef206b35"
BASE_URL = "https://payment.schibsted.no"
PODME_BASE_URL = "https://podme.com"
RETURN_URL = f"{PODME_BASE_URL}/no/oppdag"


@dataclass
class PodMeDefaultAuthClient(PodMeAuthClient):
    user_agent = DEFAULT_USER_AGENT
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

    _credentials: SchibstedCredentials | None = None
    _close_session: bool = False

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
    ):
        if base_url is None:
            base_url = BASE_URL
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
            async with async_timeout.timeout(self.request_timeout):
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

    async def async_get_access_token(self):
        if not self._credentials:
            if not self.user_credentials:
                raise PodMeApiAuthenticationError("No user credentials provided")
            credentials = await self.authorize(self.user_credentials)
        elif self._credentials.is_expired():
            credentials = await self.refresh_token()
        else:
            credentials = self._credentials
        return credentials.access_token

    async def authorize(self, user_credentials: PodMeUserCredentials):
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
                        "returnUrl": RETURN_URL,
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
        self._credentials = SchibstedCredentials.from_json(jwt_cred)

        _LOGGER.debug(f"Login successful: (final location: {final_location})")

        if self._close_session:
            await self.session.close()

        return self._credentials

    async def refresh_token(self, credentials: SchibstedCredentials | None = None):
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
        self._credentials = SchibstedCredentials.from_dict(credentials)
        _LOGGER.debug(f"Got credentials: {self._credentials}")

        if self._close_session:
            await self.session.close()
        return self._credentials

    def get_credentials(self):
        if self._credentials is not None:
            return self._credentials.to_dict()
        return None

    def set_credentials(self, credentials: SchibstedCredentials | dict | str):
        if isinstance(credentials, SchibstedCredentials):
            self._credentials = credentials
        elif isinstance(credentials, dict):
            self._credentials = SchibstedCredentials.from_dict(credentials)
        else:
            self._credentials = SchibstedCredentials.from_json(credentials)
