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
from typing import TYPE_CHECKING, Callable, Self, Sequence, TypeVar, Literal, Optional

import aiofiles
import aiofiles.os
from aiohttp.client import ClientError, ClientPayloadError, ClientResponseError, ClientSession
from aiohttp.hdrs import METH_DELETE, METH_GET, METH_POST
from ffmpeg.asyncio import FFmpeg
from ffmpeg.errors import FFmpegError
import platformdirs
from yarl import URL

from podme_api.const import (
    DEFAULT_REQUEST_TIMEOUT,
    PODME_API_URL, PODME_MOBILE_API_URL, PODME_MOBILE_USER_AGENT,
)
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
    PodMeDownloadProgressTask,
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
    from podme_api.models import FetchedFileInfo

T = TypeVar("T")

_LOGGER = logging.getLogger(__name__)


@dataclass
class PodMeClient:
    """A client for interacting with the PodMe API.

    This class provides methods to authenticate, manage user data, and interact
    with podcasts and episodes through the PodMe service.
    """

    auth_client: PodMeAuthClient
    """auth_client (PodMeAuthClient): The authentication client."""

    mobile_auth_client: PodMeAuthClient
    """mobile_auth_client (PodMeAuthClient): The mobile API authentication client."""

    user_agent = PODME_MOBILE_USER_AGENT
    """User agent string for API requests."""

    disable_credentials_storage: bool = False
    """Whether to disable credential storage."""

    language = PodMeLanguage.NO
    """(PodMeLanguage): The language setting for the client."""
    region = PodMeRegion.NO
    """(PodMeRegion): The region setting for the client."""

    request_timeout: int = DEFAULT_REQUEST_TIMEOUT
    """The timeout for API requests in seconds."""
    session: ClientSession | None = None
    """(ClientSession | None): The :class:`aiohttp.ClientSession` to use for API requests."""

    _conf_dir = platformdirs.user_config_dir(__package__, ensure_exists=True)
    _close_session: bool = False

    _supported_regions = [
        PodMeRegion.NO,
        PodMeRegion.SE,
        PodMeRegion.FI,
    ]

    def set_conf_dir(self, conf_dir: PathLike | str) -> None:
        """Set the configuration directory.

        Args:
            conf_dir (PathLike | str): The path to the configuration directory.

        """
        self._conf_dir = Path(conf_dir).resolve()

    def credentials_file_prefix_and_client(self, api_type: Literal["web", "mobile"]):
        match api_type:
            case "mobile":
                return "mobile_", self.mobile_auth_client
            case _:
                return "", self.auth_client

    async def save_credentials_to_file(
        self,
        api_type: Literal["web", "mobile"],
        filename: Optional[str] = None
    ) -> None:
        """Save credentials for the specified API type."""
        prefix, client = self.credentials_file_prefix_and_client(api_type)
        if filename is None:
            filename = Path(self._conf_dir) / f"{prefix}credentials.json"
        filename = Path(filename).resolve()
        credentials = client.get_credentials()
        if credentials is None:  # pragma: no cover
            _LOGGER.warning(f"Tried to save non-existing credentials ({api_type})")
            return
        async with aiofiles.open(filename, "w") as f:
            await f.write(json.dumps(credentials))

    async def save_credentials(self, filename: PathLike | None = None, mobile_filename: PathLike | None = None) -> None:
        """Save the current authentication credentials to a file.

        Args:
            filename (PathLike | None): The file to save the credentials to.
                If None, uses the default location.
            mobile_filename (PathLike | None): The file to save the credentials to (mobile API).
                If None, uses the default location.
        """
        await self.save_credentials_to_file('web', filename)
        await self.save_credentials_to_file('mobile', mobile_filename)

    async def load_credentials_from_file(
        self,
        api_type: Literal["web", "mobile"],
        filename: Optional[PathLike] = None
    ) -> None:
        """Load credentials for the specified API type."""
        prefix, client = self.credentials_file_prefix_and_client(api_type)

        if filename is None:
            filename = Path(self._conf_dir) / f"{prefix}credentials.json"
        filename = Path(filename).resolve()

        if not filename.exists():
            _LOGGER.warning(
                f"Credentials file does not exist: <{filename}>{' (mobile)' if api_type == 'mobile' else ''}")
            return

        async with aiofiles.open(filename) as f:
            data = await f.read()
            if data:
                client.set_credentials(data)

    async def load_credentials(self, filename: PathLike | None = None, mobile_filename: PathLike | None = None) -> None:
        """Load authentication credentials from a file.

        Args:
            filename (PathLike | None): The file to load the credentials from.
                If None, uses the default location.
            mobile_filename (PathLike | None): The file to load the credentials from (mobile API).
                If None, uses the default location.
        """
        await self.load_credentials_from_file('web', filename)
        await self.load_credentials_from_file('mobile', mobile_filename)

    def _ensure_session(self):
        if self.session is None:
            self.session = ClientSession()
            _LOGGER.debug("New session created.")
            self._close_session = True

    async def _request(  # noqa: C901
        self,
        uri: str,
        method: str = METH_GET,
        retry: int = 0,
        api: Literal["web", "mobile"] = "web",
        **kwargs,
    ) -> str | dict | list | bool | None:
        """Make a request to the PodMe API.

        Args:
            uri (str): The URI for the API endpoint.
            method (str): The HTTP method to use for the request.
            retry (int): The number of retries for the request.
            **kwargs: Additional keyword arguments for the request.
                May include:
                - params (dict): Query parameters for the request.
                - json (dict): JSON data to send in the request body.
                - headers (dict): Additional headers for the request.

        Returns:
            The response data from the API.

        """
        match api:
            case "mobile":
                base_url = PODME_MOBILE_API_URL
                access_token = await self.mobile_auth_client.async_get_access_token()
            case _:
                base_url = PODME_API_URL
                access_token = await self.auth_client.async_get_access_token()

        url = URL(f"{base_url.strip('/')}/").join(URL(uri))

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
        self._ensure_session()

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
            if response.status == HTTPStatus.UNAUTHORIZED:
                if (
                    self.auth_client.get_credentials() is None
                    or self.auth_client.user_credentials is None
                    or retry > 0
                ):
                    raise PodMeApiUnauthorizedError(
                        "Unauthorized access to the PodMe API. Please check your login credentials.",
                    )
                _LOGGER.warning(
                    "Request to <%s> resulted in status 401. Retrying after invalidating credentials.", url
                )
                self.auth_client.invalidate_credentials()
                return await self._request(uri, method, retry=retry + 1, **kwargs)

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
        uri: str,
        get_by_oldest: bool = False,
        get_pages: int | None = None,
        page_size: int | None = None,
        params: dict | None = None,
        items_key: str | None = None,
    ):
        """Retrieve multiple pages of data from the API.

        Args:
            uri: The URI for the API endpoint.
            get_by_oldest: Whether to retrieve pages by oldest first.
            get_pages: The number of pages to retrieve.
            page_size: The number of items per page.
            params: Additional parameters for the request.
            items_key: The key for the items in the response.

        Returns:
            list: The retrieved data.

        """
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
            raise

        return data

    @staticmethod
    async def transcode_file(
        input_file: PathLike | str,
        output_file: PathLike | str | None = None,
        transcode_options: dict[str, str] | None = None,
    ) -> Path:
        """Remux audio file using ffmpeg.

        This will basically remux the audio file into another container format (version 1 of the MP4
        Base Media format). Most likely this can be solved in better ways, but this will do for now.
        If the audio is served to clients in the original container (version 5 as of now), they will
        be very confused about the total duration of the file, for some reason...

        Args:
            input_file (PathLike | str): The path to the audio file.
            output_file (PathLike | str | None): The path to the output file.
                By default, the output file will be the same as the input file with "_out" appended
                to the name.
            transcode_options (dict[str, str] | None): Additional transcode options.

        """
        input_file = Path(input_file)
        if not input_file.is_file():
            raise PodMeApiError("File not found")

        if output_file is None:  # pragma: no cover
            output_file = input_file.with_stem(f"{input_file.stem}_out")

        transcode_options = transcode_options or {}

        try:
            ffprobe = FFmpeg(executable="ffprobe").input(
                input_file,
                print_format="json",
                show_streams=None,
            )
            media = json.loads(await ffprobe.execute())

            codec_name = media["streams"][0]["codec_name"]
            codec_tag_string = media["streams"][0]["codec_tag_string"]
            if codec_name == "aac" and codec_tag_string[:3] == "mp4":
                output_file = output_file.with_suffix(".mp4")
                transcode_options.update(
                    {
                        "codec": "copy",
                        "map": "0",
                        "brand": "isomiso2mp41",
                    }
                )

            elif codec_name == "mp3":
                return input_file

            _LOGGER.info("Transcoding file: %s to %s", input_file, output_file)
            ffmpeg = (
                FFmpeg()
                .option("y")
                .input(input_file)
                .output(
                    output_file,
                    transcode_options,
                )
            )
            await ffmpeg.execute()
        except FileNotFoundError as err:
            _LOGGER.warning("Please install ffmpeg to enable transcoding: %s", err)
            return input_file
        except FFmpegError as err:
            _LOGGER.warning("Error occurred while transcoding file: %s", err)
            return input_file
        return output_file

    async def download_file(
        self,
        download_url: URL | str,
        path: PathLike | str,
        on_progress: Callable[[PodMeDownloadProgressTask, str, int, int], None] | None = None,
        on_finished: Callable[[str, str], None] | None = None,
        transcode: bool = True,
    ) -> None:
        """Download a file from a given URL and save it to the specified path.

        Args:
            download_url (URL | str): The URL of the file to download.
            path (PathLike | str): The local path where the file will be saved.
            on_progress (Callable[[PodMeDownloadProgressTask, str, int, int], None], optional):
                A callback function to report download progress. It should accept
                the download URL/path, current and total as arguments (current==total means 100%).
            on_finished (Callable[[str, str], None], optional):
                A callback function to be called when the download is complete.
                It should accept the download URL and save path as arguments.
            transcode (bool, optional): Whether to transcode the file. Defaults to True.

        Raises:
            PodMeApiDownloadError: If there's an error during the download process.

        """
        download_url = URL(download_url)
        save_path = Path(path)
        if on_progress is None:
            on_progress = lambda task, url, current, total: None  # noqa: E731, ARG005
        if on_finished is None:
            on_finished = lambda url, _path: None  # noqa: E731, ARG005

        self._ensure_session()

        try:
            resp = await self.session.get(download_url, raise_for_status=True, headers={
                "User-Agent": self.user_agent
            })
            total_size = int(resp.headers.get("Content-Length", 0))
            on_progress(PodMeDownloadProgressTask.DOWNLOAD_FILE, str(download_url), 0, total_size)
            current_size = 0
            async with aiofiles.open(save_path, mode="wb") as f:
                _LOGGER.debug("Starting download of <%s>", download_url)
                async for chunk, _ in resp.content.iter_chunks():
                    await f.write(chunk)
                    current_size += len(chunk)
                    on_progress(
                        PodMeDownloadProgressTask.DOWNLOAD_FILE, str(download_url), current_size, total_size
                    )
        except (ClientPayloadError, ClientResponseError) as err:
            msg = f"Error while downloading {download_url}"
            raise PodMeApiDownloadError(msg) from err

        _LOGGER.debug("Finished download of <%s> to <%s>", download_url, save_path)

        if transcode:
            on_progress(PodMeDownloadProgressTask.TRANSCODE_FILE, str(download_url), 0, 100)
            new_save_path = await self.transcode_file(save_path)
            if new_save_path != save_path:
                _LOGGER.debug("Moving transcoded file %s to %s", new_save_path, save_path)
                await aiofiles.os.replace(new_save_path, save_path)
            on_progress(PodMeDownloadProgressTask.TRANSCODE_FILE, str(download_url), 100, 100)

        on_finished(str(download_url), str(save_path))

    async def download_files(
        self,
        download_info: list[tuple[URL | str, PathLike]],
        on_progress: Callable[[PodMeDownloadProgressTask, str, int, int], None] | None = None,
        on_finished: Callable[[str, str], None] | None = None,
    ):
        """Download multiple files concurrently.

        Args:
            download_info (list[tuple[URL | str, Path | str]]): A list of tuples containing
                the download URL and save path for each file.
            on_progress (Callable[[PodMeDownloadProgressTask, str, int, int], None], optional):
                A callback function to report download progress. It should accept
                the download URL/path, current and total as arguments (current==total means 100%).
            on_finished (Callable[[str, str], None], optional):
                A callback function to be called when the download is complete.
                It should accept the download URL and save path as arguments.

        """
        return await self._run_concurrent(
            self.download_file,
            download_info,
            on_progress=on_progress,
            on_finished=on_finished,
        )

    async def get_episode_download_url_bulk(
        self,
        episodes: list[PodMeEpisode | int],
    ) -> list[tuple[int, URL]]:
        """Get download URLs for a list of episodes.

        This method fetches download URLs for multiple episodes concurrently and
        ensures that only unique episode IDs are included in the result.

        Args:
            episodes (list[PodMeEpisode | int]): A list of PodMeEpisode objects
                or episode IDs for which to fetch download URLs.

        Returns:
            list[tuple[int, URL]]: A list of tuples, each containing an episode ID
            and its corresponding download URL. Duplicate episode IDs are removed.

        Raises:
            PodMeApiStreamUrlError: If unable to find url from m3u8, or if the url isn't downloadable.

        """
        # Extract episode IDs that need to be fetched
        episode_ids_to_fetch = [ep for ep in episodes if isinstance(ep, int)]
        episode_objects = [ep for ep in episodes if isinstance(ep, PodMeEpisode)]

        # Fetch episode data for IDs in bulk
        if episode_ids_to_fetch:
            fetched_episodes = await self.get_episodes_info(episode_ids_to_fetch)
            episode_objects.extend(fetched_episodes)

        # Process all episode objects in parallel
        async def get_url(ep):
            if ep.url is not None:
                return ep.id, URL(ep.url)
            if ep.stream_url is None:
                raise PodMeApiStreamUrlError(f"No stream URL found for episode {ep.id}")
            info = await self.resolve_stream_url(URL(ep.stream_url))
            return ep.id, URL(info["url"])

        result = await asyncio.gather(*[get_url(ep) for ep in episode_objects])

        # Filter unique IDs
        seen = set()
        filtered_result = []
        for item in result:
            if item[0] not in seen:
                seen.add(item[0])
                filtered_result.append(item)

        return filtered_result

    async def get_username(self) -> str:
        """Get the username of the authenticated user."""
        return await self._request(
            "user",
        )

    async def get_user_subscription(self) -> list[PodMeSubscription]:
        """Get the user's subscriptions."""
        subscriptions = await self._request(
            "subscription",
        )
        return [PodMeSubscription.from_dict(sub) for sub in subscriptions]

    async def get_user_podcasts(self) -> list[PodMePodcast]:
        """Get the user's podcasts."""
        podcasts = await self._get_pages(
            "podcast/userpodcasts",
        )
        return [PodMePodcast.from_dict(data) for data in podcasts]

    async def get_categories(self, region: PodMeRegion | None = None) -> list[PodMeCategory]:
        """Get podcast categories for a specific region.

        Args:
            region (PodMeRegion | None): The region to get categories for.
                If None, uses the client's default region.

        """
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
        """Get a category by its ID or key.

        Args:
            category_id (int | str): The ID or key of the category.
            region (PodMeRegion, optional): The region to get the category for.
                If None, uses the client's default region.

        """
        if isinstance(category_id, int):
            return await self.get_category_by_id(category_id, region)
        return await self.get_category_by_key(category_id, region)

    async def get_category_by_id(self, category_id: int, region: PodMeRegion | None = None) -> PodMeCategory:
        """Get a category by its ID.

        Args:
            category_id (int): The ID of the category.
            region (PodMeRegion, optional): The region to get the category for.
                If None, uses the client's default region.

        """
        categories = await self.get_categories(region)
        for c in categories:
            if c.id == category_id:
                return c
        raise PodMeApiError(f"Category with id {category_id} not found.")

    async def get_category_by_key(
        self, category_key: str, region: PodMeRegion | None = None
    ) -> PodMeCategory:
        """Get a category by its key.

        Args:
            category_key (str): The key of the category.
            region (PodMeRegion, optional): The region to get the category for.
                If None, uses the client's default region.

        """
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
        """Get the page for a specific category.

        Args:
            category (PodMeCategory | int | str): The category, its ID, or its key.
            region (PodMeRegion, optional): The region to get the category page for.
                If None, uses the client's default region.

        """
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
        """Get podcasts for a specific category.

        Args:
            category (PodMeCategory | int): The category or its ID.
            region (PodMeRegion, optional): The region to get podcasts for.
                If None, uses the client's default region.
            pages (int, optional): The number of pages to retrieve.
            page_size (int, optional): The number of items per page.

        """
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
        """Get the home screen content."""
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
        """Get popular podcasts.

        Args:
            podcast_type (int, optional): The type of podcasts to retrieve.
            category (PodMeCategory | str, optional): The category or category key to filter by.
            pages (int, optional): The number of pages to retrieve.
            page_size (int, optional): The number of items per page.

        """
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
        """Check if the user is subscribed to a podcast.

        Args:
            podcast_id (int): The ID of the podcast.

        """
        response = await self._request(
            f"bookmark/{podcast_id}",
            method=METH_GET,
        )
        return response == "true"

    async def subscribe_to_podcast(self, podcast_id: int) -> bool:
        """Subscribe to a podcast.

        Args:
            podcast_id (int): The ID of the podcast to subscribe to.

        """
        return await self._request(
            f"bookmark/{podcast_id}",
            method=METH_POST,
        )

    async def unsubscribe_to_podcast(self, podcast_id: int) -> bool:
        """Unsubscribe from a podcast.

        Args:
            podcast_id (int): The ID of the podcast to unsubscribe from.

        """
        return await self._request(
            f"bookmark/{podcast_id}",
            method=METH_DELETE,
        )

    async def scrobble_episode(
        self,
        episode_id: int,
        playback_progress: time | str | None = None,
        has_completed: bool = False,
    ) -> bool:
        """Update the playback progress for an episode.

        Args:
            episode_id (int): The ID of the episode.
            playback_progress (time | str, optional): The current playback position.
            has_completed (bool, optional): Whether the episode has been completed. Defaults to False.

        """
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
        """Get the list of currently playing episodes."""
        episodes = await self._get_pages(
            "episode/currentlyplaying",
        )
        return [PodMeEpisode.from_dict(data) for data in episodes]

    async def get_podcast_info(self, podcast_slug: str) -> PodMePodcast:
        """Get information about a podcast.

        Args:
            podcast_slug (str): The slug of the podcast.

        """
        data = await self._request(
            f"podcast/slug/{podcast_slug}",
        )
        return PodMePodcast.from_dict(data)

    async def get_podcasts_info(self, podcast_slugs: list[str]) -> list[PodMePodcast]:
        """Get information about multiple podcasts.

        Args:
            podcast_slugs (list[str]): The slugs of the podcasts.

        """
        podcasts = await asyncio.gather(*[self.get_podcast_info(slug) for slug in podcast_slugs])
        return list(podcasts)

    async def get_episode_info(self, episode_id: int) -> PodMeEpisode:
        """Get information about an episode.

        Args:
            episode_id (int): The ID of the episode.

        """
        data = await self._request(
            f"episode/{episode_id}",
        )
        base_episode = PodMeEpisode.from_dict(data)
        podcast_id = base_episode.podcast_id
        page = 0
        page_size = 50

        while True:
            # Request a page of episodes for the given podcast
            episodes_data = await self._request(
                f"episodes/podcast/{podcast_id}?page={page}&pageSize={page_size}&orderBy=0", METH_GET, 0,
                api='mobile'
            )

            # Check if we got any episodes back
            if not episodes_data or len(episodes_data) == 0:
                # No more episodes to check
                break

            # Search for the target episode in this page
            for episode_data in episodes_data:
                if episode_data.get('id') == episode_id:
                    # Found the target episode
                    return PodMeEpisode.from_dict(episode_data)

            # Move to the next page
            page += 1

        raise PodMeApiNotFoundError("Episode not found")

    async def get_episodes_info(self, episode_ids: list[int]) -> list[PodMeEpisode]:
        """Get information about multiple episodes.

        Args:
            episode_ids (list[int]): The IDs of the episodes.

        """
        episode_to_podcast = {}
        podcast_to_episodes = {}

        async def get_podcast_id(episode_id):
            data = await self._request(f"episode/{episode_id}")
            base_episode = PodMeEpisode.from_dict(data)
            return episode_id, base_episode.podcast_id

        id_results = await asyncio.gather(*[get_podcast_id(episode_id) for episode_id in episode_ids])

        for episode_id, podcast_id in id_results:
            episode_to_podcast[episode_id] = podcast_id

            if podcast_id not in podcast_to_episodes:
                podcast_to_episodes[podcast_id] = []
            podcast_to_episodes[podcast_id].append(episode_id)

        async def process_podcast(target_podcast_id, target_episode_ids):
            result_episodes = []
            page = 0
            page_size = 50
            found_episode_ids = set()

            while found_episode_ids != set(target_episode_ids):
                episodes_data = await self._request(
                    f"episodes/podcast/{target_podcast_id}?page={page}&pageSize={page_size}&orderBy=0", METH_GET, 0,
                    api='mobile'
                )

                if not episodes_data or len(episodes_data) == 0:
                    break

                for episode_data in episodes_data:
                    found_episode_id = episode_data.get('id')
                    if found_episode_id in target_episode_ids and found_episode_id not in found_episode_ids:
                        episode = PodMeEpisode.from_dict(episode_data)
                        result_episodes.append(episode)
                        found_episode_ids.add(episode.id)

                if len(found_episode_ids) == len(target_episode_ids):
                    break

                page += 1

            return result_episodes

        tasks = [process_podcast(podcast_id, episode_ids)
                 for podcast_id, episode_ids in podcast_to_episodes.items()]
        results = await asyncio.gather(*tasks)

        all_episodes = []
        for podcast_episodes in results:
            all_episodes.extend(podcast_episodes)

        episode_dict = {episode.id: episode for episode in all_episodes}
        return [episode_dict.get(episode_id) for episode_id in episode_ids]

    async def search_podcast(
        self,
        search: str,
        pages: int | None = None,
        page_size: int | None = None,
    ) -> list[PodMeSearchResult]:
        """Search for podcasts.

        Args:
            search (str): The search query.
            pages (int, optional): The number of pages to retrieve.
            page_size (int, optional): The number of items per page.

        """
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
        """Get the full list of episodes for a podcast.

        Args:
            podcast_slug (str): The slug of the podcast.

        """
        episodes = await self._get_pages(
            f"episode/slug/{podcast_slug}",
            get_by_oldest=True,
        )
        _LOGGER.debug("Retrieved full episode list, containing %s episodes", len(episodes))

        return [PodMeEpisode.from_dict(data) for data in episodes]

    async def get_latest_episodes(self, podcast_slug: str, episodes_limit: int = 20) -> list[PodMeEpisode]:
        """Get the latest episodes for a podcast.

        Args:
            podcast_slug (str): The slug of the podcast.
            episodes_limit (int, optional): The maximum number of episodes to retrieve. Defaults to 20.

        """
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
        """Get the IDs of all episodes for a podcast.

        Args:
            podcast_slug: The slug of the podcast.

        """
        episodes = await self.get_episode_list(podcast_slug)
        return [e.id for e in episodes]

    async def check_stream_url(self, stream_url: URL | str) -> FetchedFileInfo:
        """Check if a stream URL is downloadable.

        Args:
            stream_url (URL | str): The URL to check.

        Returns:
            The content length and content type if the URL is downloadable, None otherwise.

        """
        self._ensure_session()

        stream_url = URL(stream_url)

        _LOGGER.debug("Checking stream URL: <%s>", stream_url)

        # Check if the audio URL is directly downloadable
        response = await self.session.get(stream_url, headers={
            "User-Agent": self.user_agent
        })
        # Needed for acast.com, which redirects to an URL containing @ instead of %40.
        if "@" in response.url.query_string:
            stream_url = URL(str(response.url).replace("@", "%40"), encoded=True)
        else:
            stream_url = response.url

        response = await self.session.head(stream_url, allow_redirects=True, headers={
            "User-Agent": self.user_agent
        })
        if response.status != HTTPStatus.OK:
            raise PodMeApiStreamUrlError(f"Stream URL is not downloadable: <{stream_url}>")
        content_length = response.headers.get("Content-Length")
        content_type = response.headers.get("Content-Type")

        _LOGGER.debug("Stream URL is downloadable as <%s>: <%s>", content_type, stream_url)

        return {
            "content_length": int(content_length),
            "content_type": content_type,
            "url": stream_url,
        }

    async def resolve_stream_url(self, stream_url: URL | str) -> FetchedFileInfo:
        """Check if a stream URL is downloadable.

        Args:
            stream_url (URL | str): The URL to check.

        Returns:
            The content length and content type if the URL is downloadable, None otherwise.

        Raises:
            PodMeApiStreamUrlError: If unable to find url from m3u8, or if the url isn't downloadable.

        """
        stream_url = URL(stream_url)
        if "m3u8" in str(stream_url):
            return await self._resolve_m3u8_url(stream_url)
        return await self.check_stream_url(stream_url)

    async def _resolve_m3u8_url(self, master_url: URL | str) -> FetchedFileInfo:
        """Resolve a master.m3u8 URL to an audio segment URL.

        Args:
            master_url (URL | str): The URL to check.

        Returns:
            The content length and content type if the URL is downloadable, None otherwise.

        """
        self._ensure_session()
        master_url = URL(master_url)

        _LOGGER.debug("Resolving m3u8 URL: <%s>", master_url)

        # Fetch master.m3u8
        response = await self.session.get(master_url, headers={
            "User-Agent": self.user_agent
        })
        master_content = await response.text()

        # Parse master.m3u8 to get the audio playlist URL (first match only).
        audio_playlist_url: URL | None = None
        for line in master_content.splitlines():
            if ".m3u8" in line:
                audio_playlist_url = master_url.join(URL(line.strip()))
                break

        if audio_playlist_url is None:
            raise PodMeApiPlaylistUrlNotFoundError(f"Could not find audio playlist URL in <{master_url}>")

        # Fetch audio playlist
        response = await self.session.get(audio_playlist_url, headers={
            "User-Agent": self.user_agent
        })
        audio_playlist_content = await response.text()

        # Parse audio playlist to get the audio segment URL
        audio_segment_url = None
        for line in audio_playlist_content.splitlines():
            if line.startswith("#"):
                continue
            if "mp4" in line:
                audio_segment_url = audio_playlist_url.join(URL(line.strip())).with_query(None)
                break

        if not audio_segment_url:
            raise PodMeApiStreamUrlNotFoundError(
                f"Could not find audio segment URL in audio playlist: <{audio_playlist_url}>"
            )

        return await self.check_stream_url(audio_segment_url)

    @staticmethod
    async def _run_concurrent(
        func: Callable[..., T],
        args_list: Sequence[any],
        **kwargs: any,
    ) -> list[T]:
        """Run multiple asynchronous tasks concurrently.

        Args:
            func (Callable[..., T]): The asynchronous function to be executed for each task.
            args_list (Sequence[any]): A sequence of arguments or argument tuples to be
                passed to the function for each task.
            **kwargs: Additional keyword arguments to be passed to the function for all tasks.

        Returns:
            list[T]: A list of results from the executed tasks.

        """
        tasks = [func(*args, **kwargs) if isinstance(args, tuple) else func(args) for args in args_list]
        return await asyncio.gather(*tasks)

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
