"""Helpers for downloading PodMe HLS (video) episodes.

PodMe serves some episodes as AES-128 encrypted HLS streams. For those, the
episode download URL is a master playlist with video renditions alongside a
single audio-only rendition. The helpers in this module resolve that audio
rendition, fetch the init segment, key and media segments through the caller's
session (the PodMe CDN binds child URLs to the session that fetched the master),
and yield the decrypted fragmented MP4 audio in playlist order.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from http import HTTPStatus
import re
from typing import TYPE_CHECKING

from aiohttp.client_exceptions import ClientError
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from podme_api.exceptions import (
    PodMeApiHlsError,
    PodMeApiPlaylistUrlNotFoundError,
    PodMeApiStreamUrlNotFoundError,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable, Mapping

    from aiohttp import ClientSession

# Number of HLS media segments to download ahead of the segment being written.
HLS_CONCURRENCY = 8

AES_KEY_LENGTH = 16
AES_BLOCK_SIZE = 16

_BYTERANGE_PATTERN = re.compile(r"(?P<length>\d+)(?:@(?P<offset>\d+))?")
_ATTRIBUTE_PATTERN = re.compile(r'([A-Za-z0-9-]+)=("[^"]*"|[^,]*)')

ByteRange = tuple[int, int]
"""A byte range as ``(offset, length)``."""


def resolve_uri(base_url: str, uri: str) -> str:
    """Resolve a (possibly relative) playlist URI against the playlist URL.

    Uses plain string handling to preserve the exact percent-encoding of the
    Akamai tokens (``hdntl``/``hdnts``) that PodMe's CDN URLs carry. URL
    libraries tend to re-encode them, which invalidates the HMAC.

    Args:
        base_url: The URL of the playlist the URI belongs to.
        uri: A possibly relative playlist or segment URI.

    Returns:
        The absolute URI, with the base URL's query string dropped.

    """
    if uri.startswith(("http://", "https://")):
        return uri
    return base_url.split("?", 1)[0].rsplit("/", 1)[0] + "/" + uri


def find_audio_variant(master: str) -> str | None:
    """Find the audio-only variant URI in an HLS master playlist.

    Video episodes carry several ``#EXT-X-STREAM-INF`` entries; the audio-only
    one is the rendition without video codecs (no ``avc`` in its CODECS
    attribute). Its URI is on the line following the attribute line. An
    alternate audio rendition declared with ``#EXT-X-MEDIA:TYPE=AUDIO`` is used
    as a fallback.

    Args:
        master: The master playlist text.

    Returns:
        The variant URI, or None when there is no audio-only variant.

    """
    lines = master.splitlines()
    for line in lines:
        if line.startswith("#EXT-X-MEDIA:") and "TYPE=AUDIO" in line and 'URI="' in line:
            uri = line.split('URI="', 1)[1].split('"', 1)[0]
            if uri:
                return uri

    for index, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF") and "avc" not in line.lower():
            for raw_candidate in lines[index + 1 :]:
                candidate = raw_candidate.strip()
                if candidate and not candidate.startswith("#"):
                    return candidate
    return None


def select_audio_playlist_url(base_url: str, playlist: str) -> str:
    """Return the audio media playlist URL for an HLS playlist.

    Args:
        base_url: The URL the playlist was fetched from.
        playlist: The playlist text, either a master or a media playlist.

    Returns:
        The audio media playlist URL. A media playlist is returned unchanged.

    Raises:
        PodMeApiPlaylistUrlNotFoundError: When a master playlist has no
            audio-only variant.

    """
    variant = find_audio_variant(playlist)
    if variant is not None:
        return resolve_uri(base_url, variant)
    if "#EXT-X-STREAM-INF" in playlist:
        raise PodMeApiPlaylistUrlNotFoundError(
            f"Could not find audio playlist URL in <{base_url}>",
        )
    return base_url


@dataclass(frozen=True)
class HlsKey:
    """An AES-128 key from an ``#EXT-X-KEY`` tag."""

    uri: str
    iv: bytes | None = None


@dataclass(frozen=True)
class HlsSegment:
    """A media segment from an HLS media playlist."""

    uri: str
    duration: float = 0.0
    byte_range: ByteRange | None = None
    key: HlsKey | None = None


@dataclass
class HlsMediaPlaylist:
    """The parts of an HLS media playlist needed to download its audio."""

    init_uri: str | None = None
    init_byte_range: ByteRange | None = None
    media_sequence: int = 0
    segments: list[HlsSegment] = field(default_factory=list)


def _parse_attributes(value: str) -> dict[str, str]:
    """Parse an HLS attribute list into a dictionary."""
    return {match.group(1): match.group(2).strip('"') for match in _ATTRIBUTE_PATTERN.finditer(value)}


def _parse_byte_range(value: str) -> tuple[int | None, int]:
    """Parse an ``length@offset`` byte range, leaving an omitted offset as None."""
    match = _BYTERANGE_PATTERN.fullmatch(value.strip())
    if match is None:
        raise PodMeApiHlsError(f"invalid HLS byte range: {value}")
    length = int(match.group("length"))
    offset = match.group("offset")
    return (None if offset is None else int(offset), length)


def _parse_iv(value: str) -> bytes:
    """Parse an ``0x...`` initialization vector into 16 bytes."""
    iv_hex = value.removeprefix("0x").removeprefix("0X")
    try:
        iv = bytes.fromhex(iv_hex.zfill(32))
    except ValueError as err:
        raise PodMeApiHlsError(f"invalid HLS initialization vector: {value}") from err
    if len(iv) != AES_BLOCK_SIZE:
        raise PodMeApiHlsError(f"invalid HLS initialization vector: {value}")
    return iv


def parse_media_playlist(playlist: str) -> HlsMediaPlaylist:  # noqa: C901, PLR0912
    """Parse a PodMe HLS media playlist.

    Args:
        playlist: The media playlist text.

    Returns:
        The parsed playlist, including init segment, key and media segments.

    Raises:
        PodMeApiHlsError: When the playlist carries an unsupported key method
            or malformed attributes.

    """
    parsed = HlsMediaPlaylist()
    duration = 0.0
    current_key: HlsKey | None = None
    pending_range: tuple[int | None, int] | None = None
    last_range_end: dict[str, int] = {}

    for raw_line in playlist.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            try:
                duration = float(line.split(":", 1)[1].split(",", 1)[0])
            except ValueError:
                duration = 0.0
        elif line.startswith("#EXT-X-MAP:"):
            attributes = _parse_attributes(line.split(":", 1)[1])
            parsed.init_uri = attributes.get("URI")
            if byterange := attributes.get("BYTERANGE"):
                offset, length = _parse_byte_range(byterange)
                parsed.init_byte_range = (offset or 0, length)
        elif line.startswith("#EXT-X-KEY:"):
            attributes = _parse_attributes(line.split(":", 1)[1])
            method = attributes.get("METHOD", "NONE").upper()
            if method == "NONE":
                current_key = None
            elif method == "AES-128":
                key_uri = attributes.get("URI")
                if not key_uri:
                    raise PodMeApiHlsError("HLS AES-128 key is missing its URI")
                iv = _parse_iv(attributes["IV"]) if "IV" in attributes else None
                current_key = HlsKey(uri=key_uri, iv=iv)
            else:
                raise PodMeApiHlsError(f"unsupported HLS key method: {method}")
        elif line.startswith("#EXT-X-MEDIA-SEQUENCE:"):
            parsed.media_sequence = int(line.split(":", 1)[1])
        elif line.startswith("#EXT-X-BYTERANGE:"):
            pending_range = _parse_byte_range(line.split(":", 1)[1])
        elif not line.startswith("#"):
            byte_range: ByteRange | None = None
            if pending_range is not None:
                offset, length = pending_range
                # An omitted offset continues from the previous sub-range of
                # the same resource.
                start = last_range_end.get(line, 0) if offset is None else offset
                byte_range = (start, length)
                last_range_end[line] = start + length
            parsed.segments.append(
                HlsSegment(
                    uri=line,
                    duration=duration,
                    byte_range=byte_range,
                    key=current_key,
                ),
            )
            pending_range = None
            duration = 0.0

    if not parsed.segments:
        raise PodMeApiStreamUrlNotFoundError("HLS media playlist contains no segments")
    return parsed


def decrypt_segment(data: bytes, key: bytes, iv: bytes) -> bytes:
    """Decrypt one AES-128-CBC encrypted HLS segment and strip its padding.

    Args:
        data: The encrypted segment.
        key: The 16-byte AES key from the playlist's ``EXT-X-KEY``.
        iv: The 16-byte initialization vector for this segment.

    Returns:
        The decrypted segment.

    Raises:
        PodMeApiHlsError: When the segment cannot be decrypted.

    """
    if len(key) != AES_KEY_LENGTH:
        raise PodMeApiHlsError(f"HLS key is {len(key)} bytes, expected {AES_KEY_LENGTH}")
    if len(iv) != AES_BLOCK_SIZE:
        raise PodMeApiHlsError(f"HLS IV is {len(iv)} bytes, expected {AES_BLOCK_SIZE}")
    if not data or len(data) % AES_BLOCK_SIZE:
        raise PodMeApiHlsError(
            f"encrypted HLS segment is {len(data)} bytes, not {AES_BLOCK_SIZE}-aligned",
        )

    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    try:
        padded = decryptor.update(data) + decryptor.finalize()
    except ValueError as err:
        raise PodMeApiHlsError(f"HLS segment decryption failed: {err}") from err

    padding = padded[-1]
    if padding < 1 or padding > AES_BLOCK_SIZE or padded[-padding:] != bytes([padding]) * padding:
        raise PodMeApiHlsError("HLS segment has invalid PKCS7 padding")
    return padded[:-padding]


async def fetch_bytes(
    session: ClientSession,
    url: str,
    *,
    byte_range: ByteRange | None = None,
    headers: Mapping[str, str] | None = None,
) -> bytes:
    """Fetch a URL, optionally requesting a byte range.

    Args:
        session: The session that fetched the master playlist; the PodMe CDN
            binds child URLs to it, so a fresh session gets 403s.
        url: The URL to fetch.
        byte_range: An optional ``(offset, length)`` range to request.
        headers: Additional request headers.

    Returns:
        The response body.

    Raises:
        PodMeApiHlsError: On connection or HTTP errors.

    """
    request_headers = dict(headers or {})
    if byte_range is not None:
        offset, length = byte_range
        request_headers["Range"] = f"bytes={offset}-{offset + length - 1}"

    status = 0
    try:
        async with session.get(url, headers=request_headers) as response:
            response.raise_for_status()
            status = response.status
            data = await response.read()
    except (ClientError, TimeoutError, OSError) as err:
        raise PodMeApiHlsError(f"Could not fetch <{url.split('?', 1)[0]}>: {err}") from err

    if byte_range is not None:
        offset, length = byte_range
        if status == HTTPStatus.OK:
            # Some CDNs ignore Range and return the full resource.
            data = data[offset : offset + length]
        elif len(data) > length:
            data = data[:length]
    return data


async def iter_hls_audio(  # noqa: C901
    session: ClientSession,
    master_url: str,
    *,
    concurrency: int = HLS_CONCURRENCY,
    headers: Mapping[str, str] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> AsyncGenerator[bytes]:
    """Yield the audio track of a PodMe HLS episode as fragmented MP4 bytes.

    The fMP4 init segment is yielded first (when present), followed by the
    media segments in playlist order, so the output can be piped into ffmpeg.
    Up to ``concurrency`` segments are downloaded ahead of the bytes already
    yielded.

    Args:
        session: The aiohttp session that will also fetch the playlists and
            segments; it must be the session that talked to the PodMe API, as
            the CDN binds requests to it.
        master_url: The episode's HLS master or media playlist URL.
        concurrency: How many segments to download ahead.
        headers: Additional request headers for all requests.
        on_progress: Optional callback receiving ``(downloaded, total)``
            segment counts.

    Yields:
        Decrypted fragmented MP4 bytes in playback order.

    Raises:
        PodMeApiHlsError: When the stream cannot be resolved or fetched.
        PodMeApiPlaylistUrlNotFoundError: When no audio variant is available.
        PodMeApiStreamUrlNotFoundError: When the media playlist has no segments.

    """
    concurrency = max(1, concurrency)
    master = (await fetch_bytes(session, master_url, headers=headers)).decode(
        "utf-8",
        errors="replace",
    )
    playlist_url = select_audio_playlist_url(master_url, master)
    playlist_text = master
    if playlist_url != master_url:
        playlist_text = (await fetch_bytes(session, playlist_url, headers=headers)).decode(
            "utf-8",
            errors="replace",
        )
    playlist = parse_media_playlist(playlist_text)

    keys: dict[str, bytes] = {}
    for segment in playlist.segments:
        if segment.key is None or segment.key.uri in keys:
            continue
        key = await fetch_bytes(
            session,
            resolve_uri(playlist_url, segment.key.uri),
            headers=headers,
        )
        if len(key) != AES_KEY_LENGTH:
            raise PodMeApiHlsError(f"HLS key is {len(key)} bytes, expected {AES_KEY_LENGTH}")
        keys[segment.key.uri] = key

    if playlist.init_uri is not None:
        yield await fetch_bytes(
            session,
            resolve_uri(playlist_url, playlist.init_uri),
            byte_range=playlist.init_byte_range,
            headers=headers,
        )

    total = len(playlist.segments)
    if on_progress is not None:
        on_progress(0, total)

    pending: deque[asyncio.Task[bytes]] = deque()
    next_index = 0

    def start_next() -> None:
        """Queue the download of the next unqueued segment, if any."""
        nonlocal next_index
        if next_index >= total:
            return
        segment = playlist.segments[next_index]
        iv = (
            segment.key.iv
            if segment.key is not None and segment.key.iv is not None
            else (playlist.media_sequence + next_index).to_bytes(16, "big")
        )
        key = keys[segment.key.uri] if segment.key is not None else None
        pending.append(
            asyncio.create_task(
                _fetch_segment(
                    session,
                    resolve_uri(playlist_url, segment.uri),
                    key,
                    iv,
                    byte_range=segment.byte_range,
                    headers=headers,
                ),
            ),
        )
        next_index += 1

    try:
        for _ in range(concurrency):
            start_next()
        for index in range(total):
            data = await pending.popleft()
            start_next()
            if on_progress is not None:
                on_progress(index + 1, total)
            yield data
    finally:
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)


async def _fetch_segment(
    session: ClientSession,
    url: str,
    key: bytes | None,
    iv: bytes,
    *,
    byte_range: ByteRange | None = None,
    headers: Mapping[str, str] | None = None,
) -> bytes:
    """Fetch and, when encrypted, decrypt one media segment."""
    data = await fetch_bytes(session, url, byte_range=byte_range, headers=headers)
    if key is None:
        return data
    return decrypt_segment(data, key, iv)
