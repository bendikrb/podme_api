"""Tests for PodMeClient."""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock

import aiohttp
from aiohttp.web_response import Response, json_response
from aresponses import ResponsesMockServer
import pytest
from yarl import URL

from podme_api import PodMeClient, PodMeDefaultAuthClient
from podme_api.const import PODME_API_URL
from podme_api.exceptions import (
    PodMeApiConnectionError,
    PodMeApiConnectionTimeoutError,
    PodMeApiError,
    PodMeApiNotFoundError,
    PodMeApiRateLimitError,
)
from podme_api.models import (
    PodMeCategory,
    PodMeCategoryPage,
    PodMeEpisode,
    PodMeHomeScreen,
    PodMePodcast,
    PodMePodcastBase,
    PodMeRegion,
    PodMeSearchResult,
    PodMeSubscription,
    PodMeSubscriptionPlan,
)

from .helpers import CustomRoute, load_fixture_json

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

PODME_API_PATH = URL(PODME_API_URL).path


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("testuser@example.com", "qwerty123"),
    ],
)
async def test_username(aresponses: ResponsesMockServer, podme_client, username: str, password: str):
    # fixture_name = "ipcheck"
    # fixture = load_fixture_json(fixture_name)
    aresponses.add(
        URL(PODME_API_URL).host,
        f"{PODME_API_PATH}/user",
        "GET",
        Response(body=username),
    )
    async with podme_client(username, password) as client:
        result = await client.get_username()
        assert result == username


async def test_get_user_subscription(aresponses: ResponsesMockServer, podme_client):
    fixture = load_fixture_json("subscription")
    aresponses.add(
        URL(PODME_API_URL).host,
        f"{PODME_API_PATH}/subscription",
        "GET",
        json_response(data=fixture),
    )
    async with podme_client() as client:
        client: PodMeClient
        result = await client.get_user_subscription()
        assert len(result) == 1
        assert isinstance(result[0], PodMeSubscription)
        assert isinstance(result[0].subscription_plan, PodMeSubscriptionPlan)


async def test_get_user_podcasts(aresponses: ResponsesMockServer, podme_client):
    fixture = load_fixture_json("podcast_userpodcasts")
    aresponses.add(
        response=json_response(data=fixture),
        route=CustomRoute(
            host_pattern=URL(PODME_API_URL).host,
            path_pattern=f"{PODME_API_PATH}/podcast/userpodcasts",
            path_qs={"page": 0},
            method_pattern="GET",
        ),
    )
    aresponses.add(
        response=json_response(data=[]),
        route=CustomRoute(
            host_pattern=URL(PODME_API_URL).host,
            path_pattern=f"{PODME_API_PATH}/podcast/userpodcasts",
            path_qs={"page": 1},
            method_pattern="GET",
        ),
    )
    async with podme_client() as client:
        client: PodMeClient
        result = await client.get_user_podcasts()
        assert len(result) == 2
        assert all(isinstance(r, PodMePodcast) for r in result)


async def test_get_currently_playing(aresponses: ResponsesMockServer, podme_client):
    fixture = load_fixture_json("episode_currentlyplaying")
    aresponses.add(
        URL(PODME_API_URL).host,
        f"{PODME_API_PATH}/episode/currentlyplaying",
        "GET",
        json_response(data=fixture),
    )
    async with podme_client() as client:
        client: PodMeClient
        result = await client.get_currently_playing()
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(r, PodMeEpisode) for r in result)


async def test_get_categories(aresponses: ResponsesMockServer, podme_client):
    fixture = load_fixture_json("cms_categories")
    aresponses.add(
        URL(PODME_API_URL).host,
        f"{PODME_API_PATH}/cms/categories",
        "GET",
        json_response(data=fixture),
    )
    aresponses.add(
        URL(PODME_API_URL).host,
        f"{PODME_API_PATH}/cms/categories?region={PodMeRegion.NO.value}",
        "GET",
        json_response(data=fixture),
        match_querystring=True,
    )
    async with podme_client() as client:
        client: PodMeClient
        result = await client.get_categories()
        assert len(result) > 0
        assert all(isinstance(r, PodMeCategory) for r in result)

        result = await client.get_categories(region=PodMeRegion.NO)
        assert len(result) > 0
        assert all(isinstance(r, PodMeCategory) for r in result)


@pytest.mark.parametrize(
    ("category_id", "category_key"),
    [
        (222, "premium"),
    ],
)
async def test_get_category(aresponses: ResponsesMockServer, podme_client, category_id, category_key):
    fixture = load_fixture_json("cms_categories")
    aresponses.add(
        URL(PODME_API_URL).host,
        f"{PODME_API_PATH}/cms/categories",
        "GET",
        json_response(data=fixture),
    )
    aresponses.add(
        URL(PODME_API_URL).host,
        f"{PODME_API_PATH}/cms/categories?region={PodMeRegion.NO.value}",
        "GET",
        json_response(data=fixture),
        match_querystring=True,
    )

    async with podme_client() as client:
        client: PodMeClient
        result = await client.get_category(category_id)
        assert isinstance(result, PodMeCategory)
        assert result.id == category_id
        result = await client.get_category(category_key)
        assert isinstance(result, PodMeCategory)
        assert result.id == category_id


@pytest.mark.parametrize(
    ("region_name", "category_key"),
    [
        ("NO", "comedy"),
    ],
)
async def test_get_category_page(aresponses: ResponsesMockServer, podme_client, region_name, category_key):
    region = PodMeRegion[region_name]
    fixture = load_fixture_json(f"cms_categories-page_{region.name}_{category_key.upper()}")
    aresponses.add(
        URL(PODME_API_URL).host,
        f"{PODME_API_PATH}/cms/categories-page/{region.name}_{category_key.upper()}",
        "GET",
        json_response(data=fixture),
    )
    aresponses.add(
        URL(PODME_API_URL).host,
        f"{PODME_API_PATH}/cms/categories?region={region.value}",
        "GET",
        json_response(data=load_fixture_json("cms_categories")),
        match_querystring=True,
    )

    async with podme_client() as client:
        client: PodMeClient
        result = await client.get_category_page(category_key, region)
        assert isinstance(result, PodMeCategoryPage)


@pytest.mark.parametrize(
    "category_id",
    [
        222,
    ],
)
async def test_get_podcasts_by_category(aresponses: ResponsesMockServer, podme_client, category_id):
    page_size = 10
    fixture_page1 = load_fixture_json(f"podcast_category_{category_id}-page1")
    fixture_page2 = load_fixture_json(f"podcast_category_{category_id}-page2")
    aresponses.add(
        response=json_response(data=fixture_page1),
        route=CustomRoute(
            host_pattern=URL(PODME_API_URL).host,
            path_pattern=f"{PODME_API_PATH}/podcast/category/{category_id}",
            path_qs={"pageSize": page_size, "page": 0},
            method_pattern="GET",
        ),
    )
    aresponses.add(
        response=json_response(data=fixture_page2),
        route=CustomRoute(
            host_pattern=URL(PODME_API_URL).host,
            path_pattern=f"{PODME_API_PATH}/podcast/category/{category_id}",
            path_qs={"pageSize": page_size, "page": 1},
            method_pattern="GET",
        ),
    )
    async with podme_client() as client:
        client: PodMeClient
        result = await client.get_podcasts_by_category(category_id, page_size=page_size, pages=2)
        assert len(result) == page_size * 2
        assert all(isinstance(r, PodMePodcastBase) for r in result)


@pytest.mark.parametrize(
    ("podcast_type", "category"),
    [
        (2, None),
        (None, "documentary"),
    ],
)
async def test_get_popular_podcasts(aresponses: ResponsesMockServer, podme_client, podcast_type, category):
    page_size = 5
    fixture_page1 = load_fixture_json(f"podcast_popular-{podcast_type}-{category}-page1")
    fixture_page2 = load_fixture_json(f"podcast_popular-{podcast_type}-{category}-page2")
    aresponses.add(
        response=json_response(data=fixture_page1),
        route=CustomRoute(
            host_pattern=URL(PODME_API_URL).host,
            path_pattern=f"{PODME_API_PATH}/podcast/popular",
            path_qs={"podcastType": podcast_type, "category": category, "pageSize": page_size, "page": 0},
            method_pattern="GET",
        ),
    )
    aresponses.add(
        response=json_response(data=fixture_page2),
        route=CustomRoute(
            host_pattern=URL(PODME_API_URL).host,
            path_pattern=f"{PODME_API_PATH}/podcast/popular",
            path_qs={"podcastType": podcast_type, "category": category, "pageSize": page_size, "page": 1},
            method_pattern="GET",
        ),
    )
    async with podme_client() as client:
        client: PodMeClient
        result = await client.get_popular_podcasts(
            podcast_type,
            category=category,
            page_size=page_size,
            pages=2,
        )
        assert len(result) == page_size * 2
        assert all(isinstance(r, PodMePodcastBase) for r in result)


@pytest.mark.parametrize(
    "podcast_id",
    [
        1727,
    ],
)
async def test_podcast_subscription(aresponses: ResponsesMockServer, podme_client, podcast_id):
    aresponses.add(
        URL(PODME_API_URL).host,
        f"{PODME_API_PATH}/bookmark/{podcast_id}",
        "GET",
        json_response(False),
    )
    aresponses.add(
        URL(PODME_API_URL).host,
        f"{PODME_API_PATH}/bookmark/{podcast_id}",
        "POST",
        response=Response(status=201),
    )
    aresponses.add(
        URL(PODME_API_URL).host,
        f"{PODME_API_PATH}/bookmark/{podcast_id}",
        "DELETE",
        response=Response(body="", status=200),
    )

    async with podme_client() as client:
        client: PodMeClient
        sub_check = await client.is_subscribed_to_podcast(podcast_id)
        assert sub_check is False
        sub_add = await client.subscribe_to_podcast(podcast_id)
        assert sub_add is True
        sub_remove = await client.unsubscribe_to_podcast(podcast_id)
        assert sub_remove is True


@pytest.mark.parametrize(
    ("episode_id", "progress"),
    [
        (4125238, "00:00:10"),
        (4125238, None),
    ],
)
async def test_scrobble_episode(aresponses: ResponsesMockServer, podme_client, episode_id, progress):
    aresponses.add(
        URL(PODME_API_URL).host,
        f"{PODME_API_PATH}/player/update",
        "POST",
        Response(body=""),
    )
    async with podme_client() as client:
        client: PodMeClient
        result = await client.scrobble_episode(episode_id, progress)
        assert result is True


@pytest.mark.parametrize(
    "podcast_slug",
    [
        "aftenpodden",
    ],
)
async def test_get_podcast_info(aresponses: ResponsesMockServer, podme_client, podcast_slug):
    fixture = load_fixture_json(f"podcast_slug_{podcast_slug}")
    aresponses.add(
        URL(PODME_API_URL).host,
        f"{PODME_API_PATH}/podcast/slug/{podcast_slug}",
        "GET",
        json_response(data=fixture),
    )

    async with podme_client() as client:
        client: PodMeClient
        result = await client.get_podcast_info(podcast_slug)
        assert isinstance(result, PodMePodcast)


@pytest.mark.parametrize(
    "episode_id",
    [
        3612514,
    ],
)
async def test_get_episode_info(aresponses: ResponsesMockServer, podme_client, episode_id):
    fixture = load_fixture_json(f"episode_{episode_id}")
    aresponses.add(
        URL(PODME_API_URL).host,
        f"{PODME_API_PATH}/episode/{episode_id}",
        "GET",
        json_response(data=fixture),
    )

    async with podme_client() as client:
        client: PodMeClient
        result = await client.get_episode_info(episode_id)
        assert isinstance(result, PodMeEpisode)


@pytest.mark.parametrize(
    "search_query",
    [
        "podden",
    ],
)
async def test_search_podcast(aresponses: ResponsesMockServer, podme_client, search_query):
    page_size = 5
    fixture_page1 = load_fixture_json("podcast_search-page1")
    fixture_page2 = load_fixture_json("podcast_search-page2")
    aresponses.add(
        response=json_response(data=fixture_page1),
        route=CustomRoute(
            host_pattern=URL(PODME_API_URL).host,
            path_pattern=f"{PODME_API_PATH}/podcast/search",
            path_qs={"searchText": search_query, "pageSize": page_size, "page": 0},
            method_pattern="GET",
        ),
    )
    aresponses.add(
        response=json_response(data=fixture_page2),
        route=CustomRoute(
            host_pattern=URL(PODME_API_URL).host,
            path_pattern=f"{PODME_API_PATH}/podcast/search",
            path_qs={"searchText": search_query, "pageSize": page_size, "page": 1},
            method_pattern="GET",
        ),
    )

    async with podme_client() as client:
        client: PodMeClient
        result = await client.search_podcast(search_query, page_size=page_size, pages=2)
        assert isinstance(result, list)
        assert all(isinstance(r, PodMeSearchResult) for r in result)
        assert len(result) == page_size * 2


@pytest.mark.parametrize(
    "podcast_slug",
    [
        "aftenpodden",
    ],
)
async def test_get_episode_list(aresponses: ResponsesMockServer, podme_client, podcast_slug):
    page_size = 5
    fixture_page1 = load_fixture_json(f"episode_slug_{podcast_slug}-page1")
    fixture_page2 = load_fixture_json(f"episode_slug_{podcast_slug}-page2")
    aresponses.add(
        response=json_response(data=fixture_page1),
        route=CustomRoute(
            host_pattern=URL(PODME_API_URL).host,
            path_pattern=f"{PODME_API_PATH}/episode/slug/{podcast_slug}",
            path_qs={"page": 0},
            method_pattern="GET",
            repeat=3,
        ),
    )
    aresponses.add(
        response=json_response(data=fixture_page2),
        route=CustomRoute(
            host_pattern=URL(PODME_API_URL).host,
            path_pattern=f"{PODME_API_PATH}/episode/slug/{podcast_slug}",
            path_qs={"page": 1},
            method_pattern="GET",
            repeat=3,
        ),
    )
    aresponses.add(
        response=json_response(data=[]),
        route=CustomRoute(
            host_pattern=URL(PODME_API_URL).host,
            path_pattern=f"{PODME_API_PATH}/episode/slug/{podcast_slug}",
            path_qs={"page": 2},
            method_pattern="GET",
            repeat=3,
        ),
    )

    async with podme_client() as client:
        client: PodMeClient
        result = await client.get_episode_list(podcast_slug)
        assert isinstance(result, list)
        assert len(result) == page_size * 2
        assert all(isinstance(r, PodMeEpisode) for r in result)

        result = await client.get_episode_ids(podcast_slug)
        assert isinstance(result, list)
        assert len(result) == page_size * 2
        assert all(isinstance(r, int) for r in result)

        result = await client.get_latest_episodes(podcast_slug, episodes_limit=page_size)
        assert isinstance(result, list)
        assert len(result) == page_size
        assert all(isinstance(r, PodMeEpisode) for r in result)


async def test_get_home_screen(aresponses: ResponsesMockServer, podme_client):
    fixture = load_fixture_json("cms_home-screen")
    aresponses.add(
        URL(PODME_API_URL).host,
        f"{PODME_API_PATH}/cms/home-screen",
        "GET",
        json_response(data=fixture),
    )
    async with podme_client() as client:
        client: PodMeClient
        result = await client.get_home_screen()
        assert isinstance(result, PodMeHomeScreen)


async def test_no_content(aresponses: ResponsesMockServer, podme_client):
    """Test HTTP 201 response handling."""
    aresponses.add(
        URL(PODME_API_URL).host,
        f"{PODME_API_PATH}/user",
        "GET",
        aresponses.Response(status=204),
    )
    async with podme_client() as client:
        client: PodMeClient
        result = await client._request("user")
        assert result is None


async def test_timeout(aresponses: ResponsesMockServer, podme_client):
    """Test request timeout."""

    # Faking a timeout by sleeping
    async def response_handler(_: aiohttp.ClientResponse):
        """Response handler for this test."""
        await asyncio.sleep(2)
        return aresponses.Response(body="Helluu")

    aresponses.add(
        URL(PODME_API_URL).host,
        f"{PODME_API_PATH}/user",
        "GET",
        response_handler,
    )
    async with podme_client() as client:
        client: PodMeClient
        client.request_timeout = 1
        with pytest.raises((PodMeApiConnectionError, PodMeApiConnectionTimeoutError)):
            assert await client._request("user")


async def test_http_error400(aresponses: ResponsesMockServer, podme_client):
    """Test HTTP 400 response handling."""
    aresponses.add(
        URL(PODME_API_URL).host,
        f"{PODME_API_PATH}/user",
        "GET",
        aresponses.Response(text="Wtf", status=400),
    )
    async with podme_client() as client:
        client: PodMeClient
        with pytest.raises(PodMeApiError):
            assert await client._request("user")


async def test_http_error404(aresponses: ResponsesMockServer, podme_client):
    """Test HTTP 404 response handling."""
    aresponses.add(
        URL(PODME_API_URL).host,
        f"{PODME_API_PATH}/user",
        "GET",
        aresponses.Response(text="Not found", status=404),
    )

    async with podme_client() as client:
        client: PodMeClient
        with pytest.raises(PodMeApiNotFoundError):
            assert await client._request("user")


async def test_http_error429(aresponses: ResponsesMockServer, podme_client):
    """Test HTTP 429 response handling."""
    aresponses.add(
        URL(PODME_API_URL).host,
        f"{PODME_API_PATH}/user",
        "GET",
        aresponses.Response(text="Too many requests", status=429),
    )

    async with podme_client() as client:
        client: PodMeClient
        with pytest.raises(PodMeApiRateLimitError):
            assert await client._request("user")


async def test_json_error(aresponses: ResponsesMockServer, podme_client):
    """Test unexpected error handling."""
    aresponses.add(
        URL(PODME_API_URL).host,
        f"{PODME_API_PATH}/user",
        "GET",
        json_response(data={"message": "Error", "code": 418}, status=500),
    )

    async with podme_client() as client:
        client: PodMeClient
        with pytest.raises(PodMeApiError):
            assert await client._request("user")


async def test_unexpected_error(aresponses: ResponsesMockServer, podme_client):
    """Test unexpected error handling."""
    aresponses.add(
        URL(PODME_API_URL).host,
        f"{PODME_API_PATH}/user",
        "GET",
        aresponses.Response(text="Error", status=418),
    )

    async with podme_client() as client:
        client: PodMeClient
        with pytest.raises(PodMeApiError):
            assert await client._request("user")


async def test_session_close():
    auth_client = PodMeDefaultAuthClient()
    auth_client.session = AsyncMock(spec=aiohttp.ClientSession)
    auth_client._close_session = True  # pylint: disable=protected-access
    await auth_client.close()
    auth_client.session.close.assert_called_once()

    client = PodMeClient(auth_client=auth_client)
    client.session = AsyncMock(spec=aiohttp.ClientSession)
    client._close_session = True  # pylint: disable=protected-access
    await client.close()
    client.session.close.assert_called_once()


async def test_context_manager():
    async with PodMeDefaultAuthClient() as auth_client:
        assert isinstance(auth_client, PodMeDefaultAuthClient)
        async with PodMeClient(auth_client=auth_client) as client:
            assert isinstance(client, PodMeClient)
        assert client.session is None or client.session.closed
    assert auth_client.session is None or auth_client.session.closed
