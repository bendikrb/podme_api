"""PodMe API."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import time
from http import HTTPStatus
import json
import logging
import math
from pathlib import Path
import socket
from typing import TYPE_CHECKING, Callable, Self

import aiofiles
from aiohttp.client import ClientError, ClientSession
from aiohttp.hdrs import METH_DELETE, METH_GET, METH_POST
import platformdirs
from yarl import URL
from youtube_dl import YoutubeDL
from youtube_dl.utils import YoutubeDLError

from podme_api.const import (
    PODME_API_URL,
)
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
    PodMeLanguage,
    PodMePodcast,
    PodMePodcastBase,
    PodMeRegion,
    PodMeSearchResult,
    PodMeSubscription,
)

if TYPE_CHECKING:
    from os import PathLike

    from podme_api.auth.common import PodMeAuthClient

_LOGGER = logging.getLogger(__name__)


@dataclass
class PodMeClient:
    auth_client: PodMeAuthClient

    disable_credentials_storage: bool = False

    language = PodMeLanguage.NO
    region = PodMeRegion.NO

    request_timeout: int = 8
    session: ClientSession | None = None

    _conf_dir = platformdirs.user_config_dir(__package__, ensure_exists=True)
    _close_session: bool = False

    _supported_regions = [
        PodMeRegion.NO,
        PodMeRegion.SE,
        PodMeRegion.FI,
    ]

    async def save_credentials(self, filename: PathLike | None = None) -> None:
        if filename is None:
            filename = Path(self._conf_dir) / "credentials.json"
        filename = Path(filename).resolve()
        credentials = self.auth_client.get_credentials()
        if credentials is None:
            _LOGGER.warning("Tried to save non-existing credentials")
            return
        async with aiofiles.open(filename, "w") as f:
            await f.write(json.dumps(credentials))

    async def load_credentials(self, filename: PathLike | None = None) -> None:
        if filename is None:
            filename = Path(self._conf_dir) / "credentials.json"
        filename = Path(filename).resolve()
        if not filename.exists():
            return
        async with aiofiles.open(filename) as f:
            data = await f.read()
            if data:
                self.auth_client.set_credentials(data)

    async def _request(  # noqa: C901
        self,
        uri: str,
        method: str = METH_GET,
        **kwargs,
    ) -> str | dict | list | bool | None:
        """Make a request."""
        url = URL(f"{PODME_API_URL.strip('/')}/").join(URL(uri))

        access_token = await self.auth_client.async_get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            **self.request_header,
            **kwargs.get("headers", {}),
        }
        kwargs.update({"headers": headers})

        params = kwargs.get("params")
        if params is not None:
            kwargs.update(params={k: str(v) for k, v in params.items() if v is not None})

        _LOGGER.debug(
            "Executing %s API request to %s.",
            method,
            url.with_query(kwargs.get("params")),
        )
        if self.session is None:
            self.session = ClientSession()
            _LOGGER.debug("New session created.")
            self._close_session = True

        try:
            async with asyncio.timeout(self.request_timeout):
                response = await self.session.request(
                    method,
                    url,
                    **kwargs,
                )
        except asyncio.TimeoutError as exception:
            raise PodMeApiConnectionTimeoutError(
                "Timeout occurred while connecting to the PodMe API"
            ) from exception
        except (ClientError, socket.gaierror) as exception:
            raise PodMeApiConnectionError(
                "Error occurred while communicating with the PodMe API"
            ) from exception

        content_type = response.headers.get("Content-Type", "")
        content_length = int(response.headers.get("Content-Length", 0))
        # Error handling
        if (response.status // 100) in [4, 5]:
            contents = await response.read()
            response.close()

            if response.status == HTTPStatus.TOO_MANY_REQUESTS:
                raise PodMeApiRateLimitError("Rate limit error has occurred with the PodMe API")
            if response.status == HTTPStatus.NOT_FOUND:
                raise PodMeApiNotFoundError("Resource not found")
            if response.status == HTTPStatus.BAD_REQUEST:
                raise PodMeApiError("Bad request syntax or unsupported method")

            if content_type.startswith("application/json"):
                raise PodMeApiError(response.status, json.loads(contents.decode("utf8")))
            raise PodMeApiError(response.status, {"message": contents.decode("utf8")})

        if response.status == HTTPStatus.NO_CONTENT:
            _LOGGER.warning("Request to <%s> resulted in status 204.", url)
            return None
        if response.status == HTTPStatus.OK and content_length == 0:
            _LOGGER.debug("Request to <%s> resulted in status 200.", url)
            return True
        if response.status == HTTPStatus.CREATED:
            _LOGGER.debug("Request to <%s> resulted in status 201.", url)
            return True

        if "application/json" in content_type:
            result = await response.json()
            _LOGGER.debug("Response: %s", str(result))
            return result
        result = await response.text()
        _LOGGER.debug("Response: %s", str(result))
        return result

    @property
    def request_header(self) -> dict[str, str]:
        """Generate a header for HTTP requests to the server."""
        return {
            "Accept": "application/json",
            "X-Region": str(self.region),
        }

    async def _get_pages(
        self,
        uri,
        get_by_oldest=False,
        get_pages=None,
        page_size=None,
        params=None,
        items_key=None,
    ):
        get_pages = get_pages or 999
        page_size = page_size or 50
        params = params or {}
        data = []

        try:
            for page in range(get_pages):
                new_results = await self._request(
                    uri,
                    params={
                        "pageSize": page_size,
                        "page": page,
                        "getByOldest": "true" if get_by_oldest else None,
                        **params,
                    },
                )
                if not isinstance(new_results, list) and items_key is not None:
                    new_results = new_results.get(items_key, [])
                if not new_results:
                    break
                data.extend(new_results)
        except PodMeApiError as err:
            _LOGGER.warning("Error occurred while fetching pages from %s: %s", uri, err)

        return data

    @staticmethod
    def _download_episode_hook(d):
        if d["status"] == "finished":
            _LOGGER.info("Done downloading, now converting ...")

    async def download_episode(
        self,
        path,
        url,
        on_finished: Callable[[dict], None] | None = None,
    ):
        def _progress_hook(d):
            self._download_episode_hook(d)
            if on_finished is not None:
                on_finished(d)

        ydl_opts = {"logger": _LOGGER, "progress_hooks": [_progress_hook], "outtmpl": path}
        loop = asyncio.get_event_loop()
        with YoutubeDL(ydl_opts) as ydl:
            try:
                await loop.run_in_executor(None, ydl.download, [url])
                return True
            except YoutubeDLError:
                _LOGGER.fatal("youtube-dl failed to harvest from <%s> to <%s>", url, path)
                return False

    async def get_username(self) -> str:
        return await self._request(
            "user",
        )

    async def get_user_subscription(self) -> list[PodMeSubscription]:
        subscriptions = await self._request(
            "subscription",
        )
        return [PodMeSubscription.from_dict(sub) for sub in subscriptions]

    async def get_user_podcasts(self) -> list[PodMePodcast]:
        podcasts = await self._get_pages(
            "podcast/userpodcasts",
        )
        return [PodMePodcast.from_dict(data) for data in podcasts]

    async def get_categories(self, region: PodMeRegion | None = None) -> list[PodMeCategory]:
        if region is None:
            region = self.region
        response = await self._request(
            "cms/categories",
            params={
                "region": region.value,
            },
        )
        # noinspection PyTypeChecker
        categories = [
            {
                **d,
                "id": int(d["destination"]),
            }
            for d in response["categories"]
        ]
        return [PodMeCategory.from_dict(data) for data in categories]

    async def get_category(self, category_id: int | str, region: PodMeRegion | None = None) -> PodMeCategory:
        if isinstance(category_id, int):
            return await self.get_category_by_id(category_id, region)
        return await self.get_category_by_key(category_id, region)

    async def get_category_by_id(self, category_id: int, region: PodMeRegion | None = None) -> PodMeCategory:
        categories = await self.get_categories(region)
        for c in categories:
            if c.id == category_id:
                return c
        raise PodMeApiError(f"Category with id {category_id} not found.")

    async def get_category_by_key(
        self, category_key: str, region: PodMeRegion | None = None
    ) -> PodMeCategory:
        categories = await self.get_categories(region)
        for c in categories:
            if c.key == category_key:
                return c
        raise PodMeApiError(f"Category with key {category_key} not found.")

    async def get_category_page(
        self,
        category: PodMeCategory | int | str,
        region: PodMeRegion | None = None,
    ) -> PodMeCategoryPage:
        if not isinstance(category, PodMeCategory):
            category = await self.get_category(category, region)
        region_name = region.name if region is not None else self.region.name
        page_id = f"{region_name}_{category.key}"
        response = await self._request(
            f"cms/categories-page/{page_id.upper()}",
        )
        return PodMeCategoryPage.from_dict(response)

    async def get_podcasts_by_category(
        self,
        category: PodMeCategory | int,
        region: PodMeRegion | None = None,
        pages: int | None = None,
        page_size: int | None = None,
    ) -> list[PodMePodcastBase]:
        category_id = category.id if isinstance(category, PodMeCategory) else category
        region_id = region.value if region is not None else self.region.value
        podcasts = await self._get_pages(
            f"podcast/category/{category_id}",
            params={"region": region_id},
            get_pages=pages,
            page_size=page_size,
            items_key="podcasts",
        )
        return [PodMePodcastBase.from_dict(data) for data in podcasts]

    async def get_home_screen(self) -> PodMeHomeScreen:
        response = await self._request(
            "cms/home-screen",
        )
        return PodMeHomeScreen.from_dict(response)

    async def get_popular_podcasts(
        self,
        podcast_type: int | None = None,
        category: PodMeCategory | str | None = None,
        pages: int | None = None,
        page_size: int | None = None,
    ) -> list[PodMePodcastBase]:
        if podcast_type is None:
            podcast_type = 2
        if category is not None:
            category = category.key if isinstance(category, PodMeCategory) else category

        podcasts = await self._get_pages(
            "podcast/popular",
            params={
                "podcastType": podcast_type,
                "category": category,
            },
            get_pages=pages,
            page_size=page_size,
        )

        return [PodMePodcastBase.from_dict(data) for data in podcasts]

    async def is_subscribed_to_podcast(self, podcast_id: int) -> bool:
        response = await self._request(
            f"bookmark/{podcast_id}",
            method=METH_GET,
        )
        return response == "true"

    async def subscribe_to_podcast(self, podcast_id: int) -> bool:
        return await self._request(
            f"bookmark/{podcast_id}",
            method=METH_POST,
        )

    async def unsubscribe_to_podcast(self, podcast_id: int) -> bool:
        return await self._request(
            f"bookmark/{podcast_id}",
            method=METH_DELETE,
        )

    async def scrobble_episode(
        self,
        episode_id: int,
        playback_progress: time | str | None = None,
        has_completed: bool = False,
    ):
        if isinstance(playback_progress, str):
            playback_progress = time.fromisoformat(playback_progress)
        elif playback_progress is None:
            playback_progress = time()

        return await self._request(
            "player/update",
            method=METH_POST,
            json={
                "episodeId": episode_id,
                "currentSpot": playback_progress.isoformat(),
                "hasCompleted": has_completed,
            },
        )

    async def get_currently_playing(self) -> list[PodMeEpisode]:
        episodes = await self._get_pages(
            "episode/currentlyplaying",
        )
        return [PodMeEpisode.from_dict(data) for data in episodes]

    async def get_podcast_info(self, podcast_slug: str) -> PodMePodcast:
        data = await self._request(
            f"podcast/slug/{podcast_slug}",
        )
        return PodMePodcast.from_dict(data)

    async def get_episode_info(self, episode_id: int) -> PodMeEpisode:
        data = await self._request(
            f"episode/{episode_id}",
        )
        return PodMeEpisode.from_dict(data)

    async def search_podcast(
        self,
        search: str,
        pages: int | None = None,
        page_size: int | None = None,
    ) -> list[PodMeSearchResult]:
        podcasts = await self._get_pages(
            "podcast/search",
            params={
                "searchText": search,
            },
            get_pages=pages,
            page_size=page_size,
            items_key="podcasts",
        )
        return [PodMeSearchResult.from_dict(data) for data in podcasts]

    async def get_episode_list(self, podcast_slug: str) -> list[PodMeEpisode]:
        episodes = await self._get_pages(
            f"episode/slug/{podcast_slug}",
            get_by_oldest=True,
        )
        _LOGGER.debug("Retrieved full episode list, containing %s episodes", len(episodes))

        return [PodMeEpisode.from_dict(data) for data in episodes]

    async def get_latest_episodes(self, podcast_slug: str, episodes_limit: int = 20) -> list[PodMeEpisode]:
        max_per_page = 50
        pages = math.ceil(episodes_limit / max_per_page)
        page_size = min(max_per_page, episodes_limit)

        episodes = await self._get_pages(
            f"episode/slug/{podcast_slug}",
            get_pages=pages,
            page_size=page_size,
        )

        _LOGGER.debug(
            "Retrieved latest episode list (asked for max %d, got %d total)",
            episodes_limit,
            len(episodes),
        )
        return [PodMeEpisode.from_dict(data) for data in episodes]

    async def get_episode_ids(self, podcast_slug) -> list[int]:
        episodes = await self.get_episode_list(podcast_slug)
        return [e.id for e in episodes]

    async def close(self) -> None:
        """Close open client session."""
        if self.session and self._close_session:
            await self.session.close()
        if not self.disable_credentials_storage:
            await self.save_credentials()

    async def __aenter__(self) -> Self:
        """Async enter."""
        if not self.disable_credentials_storage:
            await self.load_credentials()
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        """Async exit."""
        await self.close()
