from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, quote_plus, urlencode, urlparse

from aiohttp.web_response import json_response
from aresponses import ResponsesMockServer
from aresponses.main import Route

# noinspection PyProtectedMember
from aresponses.utils import ANY, _text_matches_pattern
import orjson
from yarl import URL

from podme_api.const import PODME_AUTH_BASE_URL, PODME_AUTH_RETURN_URL, PODME_BASE_URL

if TYPE_CHECKING:
    from podme_api import SchibstedCredentials

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def save_fixture(name: str, data: dict):  # pragma: no cover
    """Save API response data to a fixture file."""
    file_path = FIXTURE_DIR / f"{name}.json"
    with open(file_path, "w") as f:
        f.write(orjson.dumps(data))


def load_fixture(name: str) -> str:
    """Load a fixture."""
    path = FIXTURE_DIR / f"{name}.json"
    if not path.exists():  # pragma: no cover
        raise FileNotFoundError(f"Fixture {name} not found")
    return path.read_text(encoding="utf-8")


def load_fixture_json(name: str) -> dict | list:
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


def setup_auth_mocks(aresponses: ResponsesMockServer, credentials: SchibstedCredentials):
    auth_flow = load_fixture_json("auth_flow")

    # GET oauth/authorize
    aresponses.add(
        URL(PODME_AUTH_BASE_URL).host,
        "/oauth/authorize",
        "GET",
        aresponses.Response(body=auth_flow["login_form"]),
        repeat=float("inf"),
    )

    # POST authn/api/settings/csrf
    aresponses.add(
        URL(PODME_AUTH_BASE_URL).host,
        "/authn/api/settings/csrf",
        "GET",
        json_response(data=auth_flow["csrf"]),
        repeat=float("inf"),
    )

    # POST authn/api/identity/email-status
    aresponses.add(
        URL(PODME_AUTH_BASE_URL).host,
        "/authn/api/identity/email-status",
        "POST",
        json_response(data=auth_flow["email_status"]),
        repeat=float("inf"),
    )

    # POST authn/api/identity/login/
    aresponses.add(
        URL(PODME_AUTH_BASE_URL).host,
        "/authn/api/identity/login/",
        "POST",
        json_response(data=auth_flow["login"]),
        repeat=float("inf"),
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
        repeat=float("inf"),
    )

    # GET https://podme.com/auth/handleSchibstedLogin
    default_credentials_json = credentials.to_json()
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
        repeat=float("inf"),
    )

    aresponses.add(
        URL(PODME_AUTH_RETURN_URL).host,
        URL(PODME_AUTH_RETURN_URL).path,
        "GET",
        aresponses.Response(
            body=auth_flow["final_html"],
        ),
        repeat=float("inf"),
    )
