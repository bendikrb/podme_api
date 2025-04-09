from __future__ import annotations

import contextlib
from datetime import datetime, timezone
import logging

import pytest

from podme_api.auth import PodMeDefaultAuthClient
from podme_api.auth.mobile_client import PodMeMobileAuthClient
from podme_api.auth.models import PodMeUserCredentials, SchibstedCredentials
from podme_api.client import PodMeClient

from .helpers import load_fixture_json

_LOGGER = logging.getLogger(__name__)

logging.basicConfig(level=logging.DEBUG)


@pytest.fixture
async def podme_client(default_credentials, user_credentials):
    """Return PodMeClient."""

    @contextlib.asynccontextmanager
    async def _podme_client(
        credentials: SchibstedCredentials | None = None,
        mobile_credentials: SchibstedCredentials | None = None,
        load_default_credentials: bool = True,
        load_default_user_credentials: bool = False,
        conf_dir: str | None = None,
    ) -> PodMeClient:
        user_creds = user_credentials if load_default_user_credentials is True else None
        auth_client = PodMeDefaultAuthClient(user_credentials=user_creds)
        mobile_auth_client = PodMeMobileAuthClient(user_credentials=user_creds)
        if credentials is not None:
            auth_client.set_credentials(credentials)
        if mobile_credentials is not None:
            mobile_auth_client.set_credentials(mobile_credentials)
        if load_default_credentials:
            auth_client.set_credentials(default_credentials)
            mobile_auth_client.set_credentials(default_credentials)
        disable_credentials_storage = conf_dir is None
        client = PodMeClient(auth_client=auth_client, mobile_auth_client=mobile_auth_client, disable_credentials_storage=disable_credentials_storage)
        if conf_dir is not None:
            _LOGGER.info("Setting configuration directory to <%s>", conf_dir)
            client.set_conf_dir(conf_dir)
        try:
            await client.__aenter__()
            yield client
        finally:
            await client.__aexit__(None, None, None)

    return _podme_client


@pytest.fixture
async def podme_default_auth_client(user_credentials, default_credentials):
    """Return PodMeDefaultAuthClient."""

    @contextlib.asynccontextmanager
    async def _podme_auth_client(
        credentials: SchibstedCredentials | None = None,
        load_default_credentials: bool = True,
        load_default_user_credentials: bool = True,
    ) -> PodMeDefaultAuthClient:
        auth_client = PodMeDefaultAuthClient()

        if load_default_user_credentials:
            auth_client.user_credentials = user_credentials
        if credentials is not None:
            auth_client.set_credentials(credentials)
        elif load_default_credentials:
            auth_client.set_credentials(default_credentials)

        try:
            await auth_client.__aenter__()
            yield auth_client
        finally:
            await auth_client.__aexit__(None, None, None)

    return _podme_auth_client


@pytest.fixture
async def podme_mobile_auth_client(user_credentials, default_credentials):
    """Return PodMeMobileAuthClient."""

    @contextlib.asynccontextmanager
    async def _podme_auth_client(
        credentials: SchibstedCredentials | None = None,
        load_default_credentials: bool = True,
        load_default_user_credentials: bool = True,
    ) -> PodMeDefaultAuthClient:
        mobile_auth_client = PodMeMobileAuthClient()

        if load_default_user_credentials:
            mobile_auth_client.user_credentials = user_credentials
        if credentials is not None:
            mobile_auth_client.set_credentials(credentials)
        elif load_default_credentials:
            mobile_auth_client.set_credentials(default_credentials)

        try:
            await mobile_auth_client.__aenter__()
            yield mobile_auth_client
        finally:
            await mobile_auth_client.__aexit__(None, None, None)

    return _podme_auth_client


@pytest.fixture
def user_credentials():
    return PodMeUserCredentials(email="testuser@example.com", password="securepassword123")


@pytest.fixture
def default_credentials():
    data = load_fixture_json("default_credentials")
    data["expiration_time"] = int(datetime.now(tz=timezone.utc).timestamp() + data["expires_in"])
    return SchibstedCredentials.from_dict(data)


@pytest.fixture
def expired_credentials():
    data = load_fixture_json("default_credentials")
    data["expiration_time"] = int(datetime.now(tz=timezone.utc).timestamp() - 1)
    return SchibstedCredentials.from_dict(data)


@pytest.fixture
def refreshed_credentials(default_credentials):
    data = load_fixture_json("default_credentials")
    data["access_token"] = data["access_token"] + "_refreshed"
    return SchibstedCredentials.from_dict(data)
