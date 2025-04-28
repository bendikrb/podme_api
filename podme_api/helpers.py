"""podme_api helper functions."""

from datetime import time
from functools import wraps


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
