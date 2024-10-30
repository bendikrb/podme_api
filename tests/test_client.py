"""Tests for PodMeClient."""

from __future__ import annotations

import asyncio
from datetime import time
import logging
from pathlib import Path
import socket
import tempfile
from unittest.mock import AsyncMock, Mock, call, patch

import aiohttp
from aiohttp.web_response import Response, json_response
from aresponses import ResponsesMockServer
import pytest
from yarl import URL

from podme_api import PodMeClient, PodMeDefaultAuthClient, SchibstedCredentials
from podme_api.const import PODME_API_URL
from podme_api.exceptions import (
    PodMeApiConnectionError,
    PodMeApiConnectionTimeoutError,
    PodMeApiDownloadError,
    PodMeApiError,
    PodMeApiNotFoundError,
    PodMeApiPlaylistUrlNotFoundError,
    PodMeApiRateLimitError,
    PodMeApiStreamUrlError,
    PodMeApiStreamUrlNotFoundError,
    PodMeApiUnauthorizedError,
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
    PodMeDownloadProgressTask,
)

from .helpers import (
    PODME_API_PATH,
    CustomRoute,
    load_fixture_json,
    setup_auth_mocks,
    setup_stream_mocks,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


def test_version():
    from podme_api.__version__ import __version__

    assert __version__ == "0.0.0"


async def test_username(aresponses: ResponsesMockServer, podme_client, default_credentials, user_credentials):
    aresponses.add(
        URL(PODME_API_URL).host,
        f"{PODME_API_PATH}/user",
        "GET",
        Response(body=user_credentials.email),
    )
    async with podme_client(credentials=default_credentials, load_default_user_credentials=True) as client:
        result = await client.get_username()
        assert result == user_credentials.email


async def test_credentials_storage(
    aresponses: ResponsesMockServer,
    podme_client,
    default_credentials,
    user_credentials,
):
    aresponses.add(
        URL(PODME_API_URL).host,
        f"{PODME_API_PATH}/user",
        "GET",
        Response(body=user_credentials.email),
        repeat=float("inf"),
    )
    with tempfile.TemporaryDirectory(delete=False) as tempdir:
        async with podme_client(
            credentials=default_credentials,
            load_default_user_credentials=True,
            conf_dir=tempdir,
        ) as client:
            result = await client.get_username()
            assert result == user_credentials.email
            await client.save_credentials()
            assert client.auth_client.get_credentials() == default_credentials.to_dict()

            creds_file = Path(tempdir) / "credentials.json"
            assert creds_file.is_file()
            stored_credentials = SchibstedCredentials.from_json(creds_file.read_text(encoding="utf-8"))
            assert stored_credentials == default_credentials

        async with podme_client(
            load_default_user_credentials=False,
            conf_dir=tempdir,
        ) as client:
            client: PodMeClient
            assert client.auth_client.get_credentials() == default_credentials.to_dict()

            result = await client.get_username()
            assert result == "testuser@example.com"

        # Test loading and saving credentials with specified filename
        async with podme_client(
            load_default_user_credentials=False,
            conf_dir=tempdir,
        ) as client:
            client: PodMeClient
            # Loading
            creds_file = Path(tempdir) / "credentials.json"
            stored_credentials = SchibstedCredentials.from_json(creds_file.read_text(encoding="utf-8"))
            await client.load_credentials(creds_file)
            assert client.auth_client.get_credentials() == stored_credentials.to_dict()

            # Saving
            creds_file_alt = creds_file.with_name("credentials2")
            await client.save_credentials(creds_file_alt)
            stored_credentials = SchibstedCredentials.from_json(creds_file_alt.read_text(encoding="utf-8"))
            assert client.auth_client.get_credentials() == stored_credentials.to_dict()


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


async def test_get_user_podcasts_error(aresponses: ResponsesMockServer, podme_client):
    aresponses.add(
        route=CustomRoute(
            host_pattern=URL(PODME_API_URL).host,
            path_pattern=f"{PODME_API_PATH}/podcast/userpodcasts",
            path_qs={"page": 0},
            method_pattern="GET",
        ),
        response=aresponses.Response(status=500),
    )
    async with podme_client() as client:
        client: PodMeClient
        with pytest.raises(PodMeApiError):
            await client.get_user_podcasts()


async def test_get_currently_playing(aresponses: ResponsesMockServer, podme_client):
    fixture = load_fixture_json("episode_currentlyplaying")
    aresponses.add(
        response=json_response(data=fixture),
        route=CustomRoute(
            host_pattern=URL(PODME_API_URL).host,
            path_pattern=f"{PODME_API_PATH}/episode/currentlyplaying",
            path_qs={"page": 0},
            method_pattern="GET",
        ),
    )
    aresponses.add(
        response=json_response(data=[]),
        route=CustomRoute(
            host_pattern=URL(PODME_API_URL).host,
            path_pattern=f"{PODME_API_PATH}/episode/currentlyplaying",
            path_qs={"page": 1},
            method_pattern="GET",
        ),
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


async def test_get_category_nonexistent(aresponses: ResponsesMockServer, podme_client):
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
        with pytest.raises(PodMeApiError):
            await client.get_category(0)
        with pytest.raises(PodMeApiError):
            await client.get_category("1")


@pytest.mark.parametrize(
    ("region_name", "category"),
    [
        ("NO", "comedy"),
        ("NO", PodMeCategory(8, "Komedi", "comedy", None)),
    ],
)
async def test_get_category_page(aresponses: ResponsesMockServer, podme_client, region_name, category):
    region = PodMeRegion[region_name]
    category_key = category.key if isinstance(category, PodMeCategory) else category

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
        result = await client.get_category_page(category, region)
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
        (4125238, time(second=10)),
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
        repeat=2,
    )

    async with podme_client() as client:
        client: PodMeClient
        result = await client.get_podcast_info(podcast_slug)
        assert isinstance(result, PodMePodcast)

        results = await client.get_podcasts_info([podcast_slug])
        assert isinstance(results, list)
        assert len(results) == 1
        assert all(isinstance(r, PodMePodcast) for r in results)


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
        repeat=2,
    )

    async with podme_client() as client:
        client: PodMeClient
        result = await client.get_episode_info(episode_id)
        assert isinstance(result, PodMeEpisode)

        result = await client.get_episodes_info([episode_id])
        assert isinstance(result, list)
        assert len(result) == 1
        assert all(isinstance(r, PodMeEpisode) for r in result)


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


async def test_download_episode_files(aresponses: ResponsesMockServer, podme_client):
    episodes_fixture = load_fixture_json("episode_currentlyplaying")
    setup_stream_mocks(aresponses, episodes_fixture)
    download_urls = [
        (e["id"], URL(e["streamUrl"]).with_name("audio_128_pkg.mp4"))
        for e in episodes_fixture
        if "m3u8" in e["streamUrl"]
    ]

    async with podme_client() as client:
        client: PodMeClient
        with tempfile.TemporaryDirectory() as d:
            dir_path = Path(d)

            def get_file_ending(url: URL) -> str:
                return url.name.rsplit(".").pop()

            download_infos = [
                (url, dir_path / f"{episode_id}.{get_file_ending(url)}") for episode_id, url in download_urls
            ]
            await client.download_files(download_infos)


async def test_download_episode_files_with_callbacks(aresponses: ResponsesMockServer, podme_client):
    episodes_fixture = load_fixture_json("episode_currentlyplaying")
    setup_stream_mocks(aresponses, episodes_fixture)
    async with podme_client() as client:
        client: PodMeClient
        on_deck = await client.get_currently_playing()
        results = await client.get_episode_download_url_bulk([*on_deck, on_deck[0].id])
        assert isinstance(results, list)
        assert len(results) == len(on_deck)

        with tempfile.TemporaryDirectory() as d:
            dir_path = Path(d)

            def get_file_ending(url: URL) -> str:
                return url.name.rsplit(".").pop()

            download_infos = [
                (url, dir_path / f"{episode_id}.{get_file_ending(url)}") for episode_id, url in results
            ]
            on_progress = Mock()
            on_finished = Mock()
            await client.download_files(download_infos, on_progress, on_finished)

            # Check progress calls
            assert on_progress.call_count > 0
            for args in on_progress.call_args_list:
                task, url, current, total = args[0]
                assert isinstance(task, PodMeDownloadProgressTask)
                assert url in [str(u) for u, _ in download_infos]
                assert 0 <= current <= total

            # Check that the last progress call for each URL has current == total
            last_calls = on_progress.call_args_list[-2:]
            for call_args in last_calls:
                _, _, current, total = call_args[0]
                assert current == total

            # Check finished calls
            assert on_finished.call_count == len(download_infos)
            on_finished.assert_has_calls(
                [call(str(url), str(file)) for url, file in download_infos], any_order=True
            )


async def test_download_episode_files_no_playlist_error(aresponses: ResponsesMockServer, podme_client):
    episodes_fixture = load_fixture_json("episode_currentlyplaying")
    setup_stream_mocks(aresponses, episodes_fixture, no_playlist_urls=True)
    async with podme_client() as client:
        client: PodMeClient
        on_deck = await client.get_currently_playing()
        with pytest.raises(PodMeApiPlaylistUrlNotFoundError):
            await client.get_episode_download_url_bulk(on_deck)


async def test_download_episode_files_no_segments_error(aresponses: ResponsesMockServer, podme_client):
    episodes_fixture = load_fixture_json("episode_currentlyplaying")
    setup_stream_mocks(aresponses, episodes_fixture, no_segment_urls=True)
    async with podme_client() as client:
        client: PodMeClient
        on_deck = await client.get_currently_playing()
        with pytest.raises(PodMeApiStreamUrlNotFoundError):
            await client.get_episode_download_url_bulk(on_deck)


async def test_download_episode_files_stream_url_check_error(aresponses: ResponsesMockServer, podme_client):
    episodes_fixture = load_fixture_json("episode_currentlyplaying")
    setup_stream_mocks(aresponses, episodes_fixture, head_request_error=True)
    async with podme_client() as client:
        client: PodMeClient
        on_deck = await client.get_currently_playing()
        with pytest.raises(PodMeApiStreamUrlError):
            await client.get_episode_download_url_bulk(on_deck)


async def test_download_episode_files_no_stream_url_error(aresponses: ResponsesMockServer, podme_client):
    episodes_fixture = load_fixture_json("episode_currentlyplaying")
    setup_stream_mocks(aresponses, episodes_fixture, no_stream_urls=True)
    async with podme_client() as client:
        client: PodMeClient
        on_deck = await client.get_currently_playing()
        with pytest.raises(PodMeApiStreamUrlError):
            await client.get_episode_download_url_bulk(on_deck)


async def test_download_episode_files_stream_url_get_error(aresponses: ResponsesMockServer, podme_client):
    episodes_fixture = load_fixture_json("episode_currentlyplaying")
    setup_stream_mocks(aresponses, episodes_fixture, get_request_error=True)
    async with podme_client() as client:
        client: PodMeClient
        on_deck = await client.get_currently_playing()
        results = await client.get_episode_download_url_bulk(on_deck)
        assert isinstance(results, list)
        assert len(results) == len(on_deck)

        with tempfile.TemporaryDirectory() as d:
            dir_path = Path(d)

            def get_file_ending(url: URL) -> str:
                return url.name.rsplit(".").pop()

            download_infos = [
                (url, dir_path / f"{episode_id}.{get_file_ending(url)}") for episode_id, url in results
            ]
            on_progress = Mock()
            on_finished = Mock()
            with pytest.raises(PodMeApiDownloadError):
                await client.download_files(download_infos, on_progress, on_finished)


async def test_transcode_file_error(podme_client):
    non_existing_file = Path("non_existing_file.mp3")

    async with podme_client() as client:
        client: PodMeClient
        with pytest.raises(PodMeApiError):
            await client.transcode_file(non_existing_file)

        with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
            invalid_file = Path(f.name)
            await client.transcode_file(invalid_file)


async def test_transcode_no_ffmpeg(monkeypatch, podme_client):
    monkeypatch.setenv("PATH", "")
    async with podme_client() as client:
        client: PodMeClient
        with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
            input_path = Path(f.name)
            saved_path = await client.transcode_file(input_path)
            assert saved_path == input_path


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
        return aresponses.Response(body="Helluu")  # pragma: no cover

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


async def test_http_error401(aresponses: ResponsesMockServer, podme_client, default_credentials):
    """Test HTTP 401 response handling."""
    # setup_auth_mocks(aresponses, default_credentials)
    aresponses.add(
        URL(PODME_API_URL).host,
        f"{PODME_API_PATH}/user",
        "GET",
        aresponses.Response(status=401),
    )
    async with podme_client() as client:
        client: PodMeClient
        with pytest.raises(PodMeApiUnauthorizedError):
            assert await client._request("user")


async def test_http_error401_with_retry(
    aresponses: ResponsesMockServer, podme_client, default_credentials, user_credentials
):
    """Test HTTP 401 with successful retry."""
    setup_auth_mocks(aresponses, default_credentials)
    aresponses.add(
        URL(PODME_API_URL).host,
        f"{PODME_API_PATH}/user",
        "GET",
        aresponses.Response(status=401),
    )
    aresponses.add(
        URL(PODME_API_URL).host,
        f"{PODME_API_PATH}/user",
        "GET",
        Response(body=user_credentials.email),
    )
    async with podme_client(load_default_user_credentials=True) as client:
        client: PodMeClient
        # with pytest.raises(PodMeApiUnauthorizedError):
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


async def test_network_error(podme_client):
    """Test network error handling."""
    async with podme_client() as client:
        client: PodMeClient
        client.session = AsyncMock(spec=aiohttp.ClientSession)
        with patch.object(client.session, "request", side_effect=socket.gaierror), pytest.raises(
            PodMeApiConnectionError
        ):
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

    client = PodMeClient(auth_client=auth_client, disable_credentials_storage=True)
    client.session = AsyncMock(spec=aiohttp.ClientSession)
    client._close_session = True  # pylint: disable=protected-access
    await client.close()
    client.session.close.assert_called_once()


async def test_context_manager(podme_default_auth_client):
    async with podme_default_auth_client() as auth_client:
        assert isinstance(auth_client, PodMeDefaultAuthClient)
        async with PodMeClient(auth_client=auth_client, disable_credentials_storage=True) as client:
            assert isinstance(client, PodMeClient)
        assert client.session is None or client.session.closed
    assert auth_client.session is None or auth_client.session.closed
