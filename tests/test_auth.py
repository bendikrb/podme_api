"""Tests for PodMeClient."""

from __future__ import annotations

from asyncio import sleep
import json
import logging
from urllib.parse import quote_plus

from aiohttp import ClientResponse
from aiohttp.web_response import json_response
from aresponses import ResponsesMockServer
import pytest
from yarl import URL

from podme_api import PodMeClient, PodMeDefaultAuthClient
from podme_api.const import PODME_AUTH_BASE_URL, PODME_AUTH_RETURN_URL, PODME_BASE_URL
from podme_api.exceptions import (
    PodMeApiAuthenticationError,
    PodMeApiConnectionError,
    PodMeApiConnectionTimeoutError,
    PodMeApiError,
)

from .helpers import load_fixture_json

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


async def test_async_get_access_token_with_valid_credentials(podme_default_auth_client, default_credentials):
    async with podme_default_auth_client() as auth_client:
        access_token = await auth_client.async_get_access_token()
        assert access_token == default_credentials.access_token

    async with PodMeDefaultAuthClient(credentials=default_credentials) as auth_client:
        access_token = await auth_client.async_get_access_token()
        assert access_token == default_credentials.access_token


async def test_async_get_access_token_with_expired_credentials(
    aresponses: ResponsesMockServer, podme_default_auth_client, expired_credentials, refreshed_credentials
):
    aresponses.add(
        URL(PODME_BASE_URL).host,
        "/auth/refreshSchibstedSession",
        "GET",
        json_response(data=refreshed_credentials.to_dict()),
    )
    async with podme_default_auth_client(credentials=expired_credentials) as auth_client:
        access_token = await auth_client.async_get_access_token()
        assert access_token == refreshed_credentials.access_token


async def test_async_get_access_token_without_credentials(podme_client, podme_default_auth_client):
    async with podme_client(load_default_credentials=False) as client:
        client: PodMeClient
        with pytest.raises(PodMeApiAuthenticationError):
            await client.auth_client.async_get_access_token()

    async with podme_default_auth_client(
        load_default_user_credentials=False, load_default_credentials=False
    ) as auth_client:
        with pytest.raises(PodMeApiAuthenticationError):
            await auth_client.async_get_access_token()


async def test_authorize_success(
    aresponses: ResponsesMockServer, podme_default_auth_client, default_credentials, user_credentials
):
    auth_flow = load_fixture_json("auth_flow")

    # GET oauth/authorize
    aresponses.add(
        URL(PODME_AUTH_BASE_URL).host,
        "/oauth/authorize",
        "GET",
        aresponses.Response(body=auth_flow["login_form"]),
        repeat=2,
    )

    # POST authn/api/settings/csrf
    aresponses.add(
        URL(PODME_AUTH_BASE_URL).host,
        "/authn/api/settings/csrf",
        "GET",
        json_response(data=auth_flow["csrf"]),
        repeat=2,
    )

    # POST authn/api/identity/email-status
    aresponses.add(
        URL(PODME_AUTH_BASE_URL).host,
        "/authn/api/identity/email-status",
        "POST",
        json_response(data=auth_flow["email_status"]),
        repeat=2,
    )

    # POST authn/api/identity/login/
    aresponses.add(
        URL(PODME_AUTH_BASE_URL).host,
        "/authn/api/identity/login/",
        "POST",
        json_response(data=auth_flow["login"]),
        repeat=2,
    )

    # POST authn/identity/finish/
    # redirect_state = quote_plus(json.dumps({""))
    redirect_state = f"%7B%22returnUrl%22%3A%22{quote_plus(PODME_AUTH_RETURN_URL)}%22%7D"
    redirect_qs = f"code=testCode&state={redirect_state}"
    aresponses.add(
        URL(PODME_AUTH_BASE_URL).host,
        "/authn/identity/finish/",
        "POST",
        aresponses.Response(
            status=302,
            headers={
                "Location": f"{PODME_BASE_URL}/auth/handleSchibstedLogin?{redirect_qs}",
            },
        ),
        repeat=2,
    )

    # GET https://podme.com/auth/handleSchibstedLogin
    default_credentials_json = default_credentials.to_json()
    default_credentials_dict = default_credentials.to_dict()
    mock_response = aresponses.Response(
        status=307,
        headers={
            "Location": PODME_AUTH_RETURN_URL,
        },
    )
    mock_response.set_cookie("jwt-cred", default_credentials_json)
    aresponses.add(
        URL(PODME_BASE_URL).host,
        "/auth/handleSchibstedLogin",
        "GET",
        mock_response,
        repeat=2,
    )

    aresponses.add(
        URL(PODME_AUTH_RETURN_URL).host,
        URL(PODME_AUTH_RETURN_URL).path,
        "GET",
        aresponses.Response(
            body=auth_flow["final_html"],
        ),
        repeat=2,
    )
    async with podme_default_auth_client(load_default_credentials=False) as auth_client:
        token = await auth_client.async_get_access_token()
        credentials = auth_client.get_credentials()
        assert credentials == default_credentials_dict
        assert token == default_credentials.access_token
        credentials = await auth_client.authorize(user_credentials)
        assert credentials == default_credentials


async def test_refresh_token_success(
    aresponses: ResponsesMockServer, podme_default_auth_client, default_credentials, refreshed_credentials
):
    # Mock the refresh token endpoint
    aresponses.add(
        URL(PODME_BASE_URL).host,
        "/auth/refreshSchibstedSession",
        "GET",
        json_response(data=refreshed_credentials.to_dict()),
    )
    async with podme_default_auth_client() as auth_client:
        new_credentials = await auth_client.refresh_token(default_credentials)
        assert new_credentials == refreshed_credentials


async def test_refresh_token_failure(aresponses: ResponsesMockServer, podme_default_auth_client):
    # Mock the refresh token endpoint to return an error
    aresponses.add(
        URL(PODME_BASE_URL).host,
        "/auth/refreshSchibstedSession",
        "GET",
        aresponses.Response(text="Unauthorized", status=401),
    )

    async with podme_default_auth_client() as auth_client:
        with pytest.raises(PodMeApiConnectionError):
            await auth_client.refresh_token()


async def test_get_set_credentials(podme_default_auth_client, default_credentials):
    async with podme_default_auth_client(load_default_credentials=False) as auth_client:
        auth_client.set_credentials(default_credentials)
        retrieved_credentials = auth_client.get_credentials()
        assert retrieved_credentials == default_credentials.to_dict()

        # Set credentials using a dictionary
        new_creds_dict = default_credentials.to_dict()
        new_creds_dict["user_id"] = "123456"
        auth_client.set_credentials(new_creds_dict)
        retrieved_new_credentials = auth_client.get_credentials()
        assert retrieved_new_credentials == new_creds_dict

        # Set credentials using a JSON string
        new_creds_json = json.dumps(new_creds_dict)
        auth_client.set_credentials(new_creds_json)
        retrieved_json_credentials = auth_client.get_credentials()
        assert retrieved_json_credentials == new_creds_dict


async def test_request_timeout(aresponses: ResponsesMockServer, podme_default_auth_client):
    # Mock a timeout by not responding
    # Faking a timeout by sleeping
    async def response_handler(_: ClientResponse):
        """Response handler for this test."""
        await sleep(1)
        return aresponses.Response(body="Helluu")  # pragma: no cover

    aresponses.add(
        URL(PODME_AUTH_BASE_URL).host,
        "/oauth/authorize",
        "GET",
        response_handler,
    )
    async with podme_default_auth_client() as auth_client:
        auth_client.request_timeout = 0.1
        with pytest.raises(PodMeApiConnectionTimeoutError):
            await auth_client._request("oauth/authorize")


async def test_request_bad_request(aresponses: ResponsesMockServer, podme_default_auth_client):
    # Mock a 400 Bad Request response
    aresponses.add(
        URL(PODME_AUTH_BASE_URL).host,
        "/invalid/endpoint",
        "GET",
        aresponses.Response(text="Bad Request", status=400),
    )
    async with podme_default_auth_client() as auth_client:
        with pytest.raises(PodMeApiError) as exc_info:
            await auth_client._request("invalid/endpoint")
        assert "Bad request syntax or unsupported method" in str(exc_info.value)
