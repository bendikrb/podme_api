from __future__ import annotations

from base64 import b64decode
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlencode, urlparse

from aiohttp.web_response import json_response
from aresponses import ResponsesMockServer
from aresponses.main import Route

# noinspection PyProtectedMember
from aresponses.utils import ANY, _text_matches_pattern
import orjson
from yarl import URL

from podme_api.const import PODME_API_BASE_URL

if TYPE_CHECKING:
    from podme_api import SchibstedCredentials
    from podme_api.auth.models import PyTestHttpFixture

PODME_API_PATH = "/mobile/api"
FIXTURE_DIR = Path(__file__).parent / "fixtures"


def save_fixture(name: str, data: dict | list):  # pragma: no cover
    """Save API response data to a fixture file."""
    file_path = FIXTURE_DIR / f"{name}.json"
    with open(file_path, "wb") as f:
        f.write(orjson.dumps(data, option=orjson.OPT_NON_STR_KEYS))


def load_fixture(name: str) -> str:
    """Load a fixture."""
    path = FIXTURE_DIR / f"{name}.json"
    if not path.exists():  # pragma: no cover
        raise FileNotFoundError(f"Fixture {name} not found")
    return path.read_text(encoding="utf-8")


def load_fixture_json(name: str):
    """Load a fixture as JSON."""
    data = load_fixture(name)
    return orjson.loads(data)


class CustomRoute(Route):  # pragma: no cover
    """Custom route for aresponses."""

    def __init__(
        self,
        method_pattern=ANY,
        host_pattern=ANY,
        path_pattern=ANY,
        path_qs=None,
        body_pattern=ANY,
        match_querystring=False,
        match_partial_query=True,
        repeat=1,
    ):
        """Initialize a CustomRoute instance.

        Args:
            method_pattern (str, optional): HTTP method to match. Defaults to ANY.
            host_pattern (str, optional): Host to match. Defaults to ANY.
            path_pattern (str, optional): Path to match. Defaults to ANY.
            body_pattern (str, optional): Body to match. Defaults to ANY.
            repeat (int, optional): Number of times to match. Defaults to 1.
            path_qs (dict, optional): Query string parameters to match.
            match_querystring (bool, optional): Whether to match the query string.
                Defaults to True if `path_qs` is not None.
            match_partial_query (bool, optional): Whether to match only part of the query string.

                If `True`, the route will match if the query string contains all the specified query
                parameters, regardless of other parameters present.

                If `False`, the route will only match if the query string exactly matches the specified
                query parameters in `path_qs`.

        """
        super().__init__(method_pattern, host_pattern, path_pattern, body_pattern, match_querystring, repeat)
        if path_qs is not None:
            self.path_qs = urlencode({k: v for k, v in path_qs.items() if v is not None})
            self.match_querystring = True
            self.match_partial_query = match_partial_query

    async def matches(self, request):
        """Check if the request matches this route.

        Args:
            request: The incoming request to match against.

        """
        path_to_match = urlparse(request.path_qs)
        query_to_match = parse_qs(path_to_match.query)
        parsed_path = urlparse(self.path_pattern)
        parsed_query = parse_qs(self.path_qs) if self.path_qs else parse_qs(parsed_path.query)

        if not _text_matches_pattern(self.host_pattern, request.host):
            return False

        if parsed_path.path != path_to_match.path:
            return False

        if self.match_querystring:
            if not self.match_partial_query and query_to_match != parsed_query:
                return False
            for key, value in parsed_query.items():
                if key not in query_to_match or query_to_match[key] != value:
                    return False

        if not _text_matches_pattern(self.method_pattern.lower(), request.method.lower()):  # noqa: SIM103
            return False

        return True


def setup_auth_mocks(aresponses: ResponsesMockServer, credentials: SchibstedCredentials | None = None):
    filter_headers = [
        "Content-Type",
        "Location",
        "Set-Cookie",
        "RateLimit-Limit",
        "RateLimit-Remaining",
        "RateLimit-Reset",
        "x-session-id",
    ]
    auth_flow = [
        "authorize_1_oauth-authorize",
        "authorize_2_login",
        "authorize_3_authn-api-settings-csrf",
        "authorize_4_authn-api-identity-login",
        "authorize_5_authn-identity-finish",
        "authorize_6_oauth-finalize",
        "authorize_7_oauth-token",
    ]
    for step in auth_flow:
        fixture: PyTestHttpFixture = load_fixture_json(step)
        url = URL(fixture["url"])
        headers = {h: fixture["headers"][h] for h in filter_headers if h in fixture["headers"]}
        response = aresponses.Response(
            status=fixture["status"],
            body=fixture["body"],
            headers=headers,
        )
        if credentials is not None and step == "authorize_8_oauth-token":
            response = json_response(data=credentials.to_dict())
        aresponses.add(
            url.host,
            url.path,
            fixture["method"],
            response,
            repeat=float("inf"),
        )


def setup_stream_mocks(
    aresponses: ResponsesMockServer,
    episodes_fixture,
    no_stream_urls=False,
    no_playlist_urls=False,
    no_segment_urls=False,
    head_request_error=False,
    get_request_error=False,
):
    if no_stream_urls:
        episodes_fixture = [
            {k: v for k, v in ep.items() if k not in ["smoothStreamingUrl"]} for ep in episodes_fixture
        ]

    aresponses.add(
        route=CustomRoute(
            host_pattern=URL(PODME_API_BASE_URL).host,
            path_pattern=f"{PODME_API_PATH}/v2/episodes/continue",
            path_qs={"page": 0},
            method_pattern="GET",
        ),
        response=json_response(data=episodes_fixture),
    )
    aresponses.add(
        route=CustomRoute(
            host_pattern=URL(PODME_API_BASE_URL).host,
            path_pattern=f"{PODME_API_PATH}/v2/episodes/continue",
            path_qs={"page": 1},
            method_pattern="GET",
        ),
        response=json_response(data=[]),
    )
    m3u8_fixture = load_fixture_json("stream_m3u8")
    mp3_fixture = load_fixture_json("stream_mp3")
    files = {
        "audio_128_pkg.mp4": b64decode(m3u8_fixture["audio_128_pkg.mp4"]),
        "normal.mp3": b64decode(mp3_fixture["normal.mp3"]),
    }

    for episode_fixture in episodes_fixture:
        stream_url = URL(episode_fixture.get("smoothStreamingUrl") or episode_fixture.get("url"))
        if "m3u8" in stream_url.path:
            resp = {
                "body": m3u8_fixture["master.m3u8"],
                "headers": {"Content-Type": "application/x-mpegURL"},
            }
            if no_playlist_urls:
                resp["body"] = "#EXTM3U\n#EXT-X-VERSION:7\n"
            aresponses.add(
                stream_url.host,
                stream_url.path,
                "GET",
                aresponses.Response(**resp),
                repeat=float("inf"),
            )

            resp = {
                "body": m3u8_fixture["audio_128_pkg.m3u8"],
                "headers": {"Content-Type": "application/x-mpegURL"},
            }
            if no_segment_urls:
                resp = {"status": 404}

            aresponses.add(
                stream_url.host,
                stream_url.with_name("audio_128_pkg.m3u8").path,
                "GET",
                aresponses.Response(**resp),
                repeat=float("inf"),
            )

            resp = {
                "headers": {
                    "Accept-Ranges": "bytes",
                    "Content-Type": "video/mp4",
                    "Content-Length": str(len(files["audio_128_pkg.mp4"])),
                }
            }

            if head_request_error:
                resp = {"status": 404}
            aresponses.add(
                stream_url.host,
                stream_url.with_name("audio_128_pkg.mp4").path,
                "HEAD",
                aresponses.Response(**resp),
                repeat=float("inf"),
            )

            resp = {
                "body": files["audio_128_pkg.mp4"],
                "headers": {
                    "Content-Type": "video/mp4",
                    "Content-Length": str(len(files["audio_128_pkg.mp4"])),
                },
            }
            if get_request_error:
                resp = {"status": 500}
            aresponses.add(
                stream_url.host,
                stream_url.with_name("audio_128_pkg.mp4").path,
                "GET",
                aresponses.Response(**resp),
                repeat=float("inf"),
            )
        else:
            redirect_url = stream_url.with_name(f"redir_{stream_url.name}")
            resp = {
                "status": 302,
                "headers": {
                    "Location": str(redirect_url),
                },
            }
            if "acast" in redirect_url.path:
                resp["headers"]["Location"] = f"{redirect_url.with_query(None)}?pf=rss&sv=sphinx%401.221.1"

            if head_request_error:
                resp = {"status": 404}
            aresponses.add(
                stream_url.host,
                stream_url.path,
                "HEAD",
                aresponses.Response(**resp),
                repeat=float("inf"),
            )

            resp = {
                "headers": {
                    "Accept-Ranges": "bytes",
                    "Content-Type": "audio/mpeg",
                    "Content-Length": str(len(files["normal.mp3"])),
                }
            }
            aresponses.add(
                redirect_url.host,
                redirect_url.path,
                "HEAD",
                aresponses.Response(**resp),
                repeat=float("inf"),
            )

            resp = {
                "status": 302,
                "headers": {
                    "Location": str(redirect_url),
                },
            }
            if "acast" in redirect_url.path:
                resp["headers"]["Location"] = f"{redirect_url.with_query(None)}?pf=rss&sv=sphinx%401.221.1"

            if get_request_error:
                resp = {"status": 500}
            aresponses.add(
                stream_url.host,
                stream_url.path,
                "GET",
                aresponses.Response(**resp),
                repeat=float("inf"),
            )

            resp = {
                "body": files["normal.mp3"],
                "headers": {
                    "Content-Type": "audio/mpeg",
                    "Content-Length": str(len(files["normal.mp3"])),
                },
            }
            aresponses.add(
                redirect_url.host,
                redirect_url.path,
                "GET",
                aresponses.Response(**resp),
                repeat=float("inf"),
            )

        # Add response for episode info
        aresponses.add(
            URL(PODME_API_BASE_URL).host,
            f'{PODME_API_PATH}/v2/episodes/{episode_fixture["id"]}',
            "GET",
            json_response(data=episode_fixture),
            repeat=float("inf"),
        )
