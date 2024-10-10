from __future__ import annotations

import contextlib
import logging

import pytest

from podme_api.auth import PodMeDefaultAuthClient, PodMeUserCredentials, SchibstedCredentials
from podme_api.client import PodMeClient

from .helpers import load_fixture

_LOGGER = logging.getLogger(__name__)

logging.basicConfig(level=logging.DEBUG)


@pytest.fixture
async def podme_client(default_credentials):
    """Return PodMeClient."""

    @contextlib.asynccontextmanager
    async def _podme_client(
        username: str | None = None,
        password: str | None = None,
        load_default_credentials: bool = True,
    ) -> PodMeClient:
        if username is None or password is None:
            user_creds = None
        else:
            user_creds = PodMeUserCredentials(username, password)
        auth_client = PodMeDefaultAuthClient(user_credentials=user_creds)
        if load_default_credentials:
            auth_client.set_credentials(default_credentials)
        client = PodMeClient(auth_client=auth_client, disable_credentials_storage=True)
        try:
            await client.__aenter__()
            yield client
        finally:
            await client.__aexit__(None, None, None)

    return _podme_client


@pytest.fixture
def default_credentials():
    data = load_fixture("default_credentials")
    return SchibstedCredentials.from_json(data)
