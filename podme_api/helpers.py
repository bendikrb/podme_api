"""podme_api helper functions."""

from __future__ import annotations

from functools import wraps
import logging
from typing import TYPE_CHECKING

from aiohttp.client_exceptions import (
    ClientError,
    NonHttpUrlRedirectClientError,
)
from yarl import URL

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from datetime import time

    from aiohttp import ClientResponse, ClientSession


def async_cache(func):
    cache = {}

    @wraps(func)
    async def wrapper(self, slug):
        if slug in cache:
            return cache[slug]
        result = await func(self, slug)
        cache[slug] = result
        return result

    return wrapper


def get_total_seconds(t: time) -> int:
    """Get the total number of seconds in a time object."""
    return t.hour * 3600 + t.minute * 60 + t.second


async def fetch_with_redirects(
    url: str | URL,
    session: ClientSession,
    max_redirects=5,
    **kwargs,
) -> ClientResponse:
    """Fetch a URL with redirects (needed to apply acast.com url rewrite)."""
    current_url = URL(url)
    for _ in range(max_redirects):
        response = await session.get(
            current_url,
            allow_redirects=False,
            **kwargs,
        )
        if response.status in (301, 302, 303, 307, 308):
            location = response.headers.get("Location")
            if not location:
                raise NonHttpUrlRedirectClientError("No location header in redirect")
            current_url = URL(current_url).join(URL(location))
            # Weird quirk needed for acast.com URLs containing @ instead of %40.
            if "@" in current_url.query_string:
                current_url = URL(str(current_url).replace("@", "%40"), encoded=True)
            continue
        return response
    raise ClientError(f"Too many redirects (>{max_redirects}) for {url}")
