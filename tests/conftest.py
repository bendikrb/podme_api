from __future__ import annotations

import contextlib
from datetime import UTC, datetime
import logging
import os
from typing import TYPE_CHECKING

import orjson
import pytest
from yarl import URL

from podme_api.auth import PodMeDefaultAuthClient
from podme_api.auth.models import PodMeUserCredentials, SchibstedCredentials
from podme_api.client import PodMeClient

from .helpers import load_fixture_json

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

_LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


def pytest_addoption(parser):
    """Add command-line option to update JSON fixtures from live API.
    Requires PODME_USER_EMAIL and PODME_USER_PASSWORD env vars for login.
    """
    parser.addoption(
        "--update-fixtures",
        action="store_true",
        default=False,
        help="Update JSON fixtures from live API (requires PODME_USER_EMAIL and PODME_USER_PASSWORD)",
    )


@pytest.fixture(scope="session")
def update_fixtures(pytestconfig):  # pragma: no cover
    """Session-wide flag to indicate fixtures should be updated from live API."""
    return pytestconfig.getoption("update_fixtures")


@pytest.fixture
async def podme_client(default_credentials, user_credentials):
    """Return PodMeClient."""

    @contextlib.asynccontextmanager
    async def _podme_client(
        credentials: SchibstedCredentials | None = None,
        load_default_credentials: bool = True,
        load_default_user_credentials: bool = False,
        conf_dir: str | None = None,
    ) -> AsyncGenerator[PodMeClient, None]:
        user_creds = user_credentials if load_default_user_credentials is True else None
        auth_client = PodMeDefaultAuthClient(user_credentials=user_creds)
        if credentials is not None:
            auth_client.set_credentials(credentials)
        elif load_default_credentials:
            auth_client.set_credentials(default_credentials)
        disable_credentials_storage = conf_dir is None
        client = PodMeClient(auth_client=auth_client, disable_credentials_storage=disable_credentials_storage)
        if conf_dir is not None:
            _LOGGER.info("Setting configuration directory to <%s>", conf_dir)
            client.set_conf_dir(conf_dir)
        try:
            await client.__aenter__()
            yield client
        finally:
            await client.__aexit__(None, None, None)

    return _podme_client


def pytest_configure(config):  # pragma: no cover
    if config.getoption("update_fixtures"):
        # Disable HTTP mocking to allow real API requests for fixture updates
        pm = config.pluginmanager
        with contextlib.suppress(Exception):
            pm.set_blocked("aresponses")
        plugin = pm.get_plugin("aresponses")
        if plugin:
            pm.unregister(plugin)

        # Enable live fixture updates
        os.environ["UPDATE_FIXTURES"] = "1"
        missing = [v for v in ("PODME_USER_EMAIL", "PODME_USER_PASSWORD") if not os.getenv(v)]
        if missing:
            raise pytest.UsageError(f"--update-fixtures requires environment variables: {', '.join(missing)}")
        import asyncio

        from podme_api.auth import PodMeDefaultAuthClient
        from podme_api.auth.models import PodMeUserCredentials
        from podme_api.client import PodMeClient

        from .helpers import save_fixture

        # noinspection PyProtectedMember
        async def _update_fixtures():
            # Setup authentication
            email = os.getenv("PODME_USER_EMAIL")
            password = os.getenv("PODME_USER_PASSWORD")
            user_creds = PodMeUserCredentials(email=email, password=password)
            auth_client = PodMeDefaultAuthClient(user_credentials=user_creds)
            client = PodMeClient(auth_client=auth_client, disable_credentials_storage=True)
            mock_credentials = load_fixture_json("mock_credentials")

            # Enter contexts
            await auth_client.__aenter__()
            await client.__aenter__()
            try:
                # get_username()
                user = await client._request("v2/user")
                user["email"] = mock_credentials["email"]
                user["userId"] = user["userAccountId"] = mock_credentials["account_id"]
                save_fixture("v2_user", user)

                # get_user_subscription()
                subscriptions = await client._request("v2/subscriptions")
                save_fixture("v2_subscriptions", subscriptions)

                # get_user_podcasts()
                userpods = await client._request(
                    "v2/podcasts/mypodcasts",
                    params={"page": 0, "pageSize": 2},
                )
                save_fixture("v2_podcasts_mypodcasts", userpods)

                # get_saved_episodes()
                saved_list = await client._request(
                    "v2/playlist/saved-list",
                    params={"page": 0, "pageSize": 2},
                )
                save_fixture("v2_playlist_saved-list", saved_list)

                # get_categories()
                categories = await client._request("v2/podcasts/categories")
                save_fixture("v2_podcasts_categories", categories)

                # get_currently_playing()
                episode1 = await client._request("v2/episodes/4125238")
                episode2 = await client._request("v2/episodes/1360289")
                episode3 = await client._request("v2/episodes/1936396")
                save_fixture("v2_episodes_4125238", episode1)
                save_fixture("v2_episodes_1360289", episode2)
                save_fixture("v2_episodes_1936396", episode3)
                save_fixture("v2_episodes_continue", [episode1, episode2, episode3])

                # get_podcasts_by_category()
                results = await client._request(
                    "v2/podcasts/search",
                    params={"categoryId": 222, "premium": "true", "pageSize": 10, "page": 0},
                )
                save_fixture("v2_podcasts_search_222-page1", results)
                results = await client._request(
                    "v2/podcasts/search",
                    params={"categoryId": 222, "premium": "true", "pageSize": 10, "page": 1},
                )
                save_fixture("v2_podcasts_search_222-page2", results)

                # get_podcast_info()
                results = await client._request("v2/podcasts/slug/aftenpodden")
                save_fixture("v2_podcasts_slug_aftenpodden", results)

                # get_episode_info()
                results = await client._request("v2/episodes/3612514")
                save_fixture("v2_episodes_3612514", results)

                # search_podcast()
                results = await client._request(
                    "v2/podcasts/search",
                    params={"searchText": "podden", "pageSize": 2, "page": 0},
                )
                save_fixture("v2_podcasts_search-podden-page1", results)

                # get_episode_list()
                results1 = await client._request(
                    "v2/episodes/podcast/1727",
                    params={"page": 0, "pageSize": 2},
                )
                save_fixture("v2_episodes_podcast_aftenpodden-page1", results1)
                results2 = await client._request(
                    "v2/episodes/podcast/1727",
                    params={"page": 1, "pageSize": 2},
                )
                save_fixture("v2_episodes_podcast_aftenpodden-page2", results2)

                # authentication fixtures
                auth_fixtures = auth_client.get_pytest_recordings()
                for sess_name in auth_fixtures:
                    for rec in auth_fixtures[sess_name]:
                        if rec["fixture_name"] == "authorize_4_authn-api-identity-email-status":
                            body = orjson.loads(rec["body"])
                            body["data"]["attributes"]["email"] = mock_credentials["email"]
                            rec["body"] = orjson.dumps(body).decode("utf-8")
                        if rec["fixture_name"] == "authorize_5_authn-api-identity-login":
                            body = orjson.loads(rec["body"])
                            body["meta"]["tracking"]["userIdentifier"] = mock_credentials["user_id"]
                            rec["body"] = orjson.dumps(body).decode("utf-8")
                        if rec["fixture_name"] == "authorize_6_authn-identity-finish":
                            location = URL(rec["headers"]["Location"]).with_query(
                                {
                                    "data": mock_credentials["id_token"],
                                }
                            )
                            rec["headers"]["Location"] = str(location)
                            rec["body"] = (
                                f'<p>Found. Redirecting to <a href="{location!s}">{location!s}</a></p>'
                            )
                        if rec["fixture_name"] == "authorize_7_oauth-finalize":
                            location = URL(rec["headers"]["Location"]).with_query(
                                {
                                    "code": mock_credentials["code"],
                                }
                            )
                            rec["headers"]["Location"] = str(location)
                            rec["body"] = ""
                        if rec["fixture_name"] == "authorize_8_oauth-token":
                            body = orjson.loads(rec["body"])
                            body["access_token"] = mock_credentials["access_token"]
                            body["refresh_token"] = mock_credentials["refresh_token"]
                            body["id_token"] = mock_credentials["id_token"]
                            rec["body"] = orjson.dumps(body).decode("utf-8")

                        save_fixture(rec["fixture_name"], rec)

            finally:
                # Exit contexts
                await client.__aexit__(None, None, None)
                await auth_client.__aexit__(None, None, None)

        # Run the update and exit pytest
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_update_fixtures())
        pytest.exit("JSON fixtures updated from live API", returncode=0)


@pytest.fixture
async def podme_default_auth_client(user_credentials, default_credentials):
    """Return PodMeDefaultAuthClient."""

    @contextlib.asynccontextmanager
    async def _podme_auth_client(
        credentials: SchibstedCredentials | None = None,
        load_default_credentials: bool = True,
        load_default_user_credentials: bool = True,
    ) -> AsyncGenerator[PodMeDefaultAuthClient, None]:
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
def mock_credentials():
    return load_fixture_json("mock_credentials")


@pytest.fixture
def user_credentials(mock_credentials):
    return PodMeUserCredentials(email=mock_credentials["email"], password=mock_credentials["password"])


@pytest.fixture
def default_credentials(mock_credentials):
    return SchibstedCredentials.from_dict(
        {
            "scope": mock_credentials["scope"],
            "token_type": mock_credentials["token_type"],
            "access_token": mock_credentials["access_token"],
            "refresh_token": mock_credentials["refresh_token"],
            "id_token": mock_credentials["id_token"],
            "expires_in": mock_credentials["expires_in"],
            "expiration_time": int(datetime.now(tz=UTC).timestamp() + mock_credentials["expires_in"]),
        }
    )


@pytest.fixture
def expired_credentials(default_credentials):
    data = default_credentials.to_dict()
    data["expiration_time"] = int(datetime.now(tz=UTC).timestamp() - 1)
    return SchibstedCredentials.from_dict(data)


@pytest.fixture
def refreshed_credentials(default_credentials):
    data = default_credentials.to_dict()
    data["access_token"] = data["access_token"] + "_refreshed"
    return SchibstedCredentials.from_dict(data)
