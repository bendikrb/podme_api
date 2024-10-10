from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from aresponses.main import Route

# noinspection PyProtectedMember
from aresponses.utils import ANY, _text_matches_pattern
import orjson

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
        super().__init__(method_pattern, host_pattern, path_pattern, body_pattern, match_querystring, repeat)
        if path_qs is not None:
            self.path_qs = urlencode({k: v for k, v in path_qs.items() if v is not None})
            self.match_querystring = True
            self.match_partial_query = match_partial_query

    async def matches(self, request):
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
