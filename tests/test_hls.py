from __future__ import annotations

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import pytest

from podme_api.exceptions import (
    PodMeApiHlsError,
    PodMeApiPlaylistUrlNotFoundError,
    PodMeApiStreamUrlNotFoundError,
)
from podme_api.hls import (
    decrypt_segment,
    fetch_bytes,
    find_audio_variant,
    parse_media_playlist,
    resolve_uri,
    select_audio_playlist_url,
)

from .helpers import encrypt_aes128

MASTER_PLAYLIST = """#EXTM3U
#EXT-X-VERSION:7
#EXT-X-STREAM-INF:BANDWIDTH=2050000,CODECS="avc1.4d401f,mp4a.40.2",RESOLUTION=1280x720
video_720.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=140800,CODECS="mp4a.40.2"
audio_128_pkg.m3u8
"""

MASTER_WITH_MEDIA_AUDIO = """#EXTM3U
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",NAME="audio",URI="alternate_audio.m3u8"
#EXT-X-STREAM-INF:BANDWIDTH=2050000,CODECS="avc1.4d401f,mp4a.40.2",AUDIO="audio"
video_720.m3u8
"""

MEDIA_PLAYLIST = """#EXTM3U
#EXT-X-VERSION:7
#EXT-X-TARGETDURATION:2
#EXT-X-MEDIA-SEQUENCE:7
#EXT-X-PLAYLIST-TYPE:VOD
#EXT-X-MAP:URI="audio_128_pkg.mp4",BYTERANGE="802@0"
#EXT-X-KEY:METHOD=AES-128,URI="key.bin",IV=0x000102030405060708090a0b0c0d0e0f
#EXTINF:2.005333,
#EXT-X-BYTERANGE:33091@802
audio_128_pkg.mp4
#EXTINF:1.701750,
#EXT-X-BYTERANGE:28106
audio_128_pkg.mp4
#EXT-X-ENDLIST
"""


def test_resolve_uri_relative_and_absolute():
    base = "https://cdn.example.com/path/master.m3u8?hdnts=exp%3D1%26hmac%3Dabc"
    assert resolve_uri(base, "audio.m3u8") == "https://cdn.example.com/path/audio.m3u8"
    assert resolve_uri(base, "https://other.example.com/audio.m3u8") == "https://other.example.com/audio.m3u8"


def test_resolve_uri_does_not_reencode_tokens():
    base = "https://cdn.example.com/path/master.m3u8"
    uri = "audio.m3u8?hdnts=exp%3D1700000000%26hmac%3Dabc%2Bdef"
    assert resolve_uri(base, uri) == f"https://cdn.example.com/path/{uri}"


def test_find_audio_variant():
    assert find_audio_variant(MASTER_PLAYLIST) == "audio_128_pkg.m3u8"
    assert find_audio_variant(MASTER_WITH_MEDIA_AUDIO) == "alternate_audio.m3u8"


def test_find_audio_variant_none():
    assert find_audio_variant('#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1,CODECS="avc1"\nv.m3u8\n') is None
    assert find_audio_variant("#EXTM3U\n") is None


def test_select_audio_playlist_url():
    base = "https://cdn.example.com/path/master.m3u8"
    assert (
        select_audio_playlist_url(base, MASTER_PLAYLIST) == "https://cdn.example.com/path/audio_128_pkg.m3u8"
    )
    assert select_audio_playlist_url(base, MEDIA_PLAYLIST) == base


def test_select_audio_playlist_url_no_audio_variant():
    with pytest.raises(PodMeApiPlaylistUrlNotFoundError):
        select_audio_playlist_url(
            "https://cdn.example.com/master.m3u8",
            '#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1,CODECS="avc1"\nvideo.m3u8\n',
        )


def test_parse_media_playlist():
    playlist = parse_media_playlist(MEDIA_PLAYLIST)

    assert playlist.init_uri == "audio_128_pkg.mp4"
    assert playlist.init_byte_range == (0, 802)
    assert playlist.media_sequence == 7
    assert len(playlist.segments) == 2

    first, second = playlist.segments
    assert first.uri == "audio_128_pkg.mp4"
    assert first.duration == pytest.approx(2.005333)
    assert first.byte_range == (802, 33091)
    assert first.key is not None
    assert first.key.uri == "key.bin"
    assert first.key.iv == bytes.fromhex("000102030405060708090a0b0c0d0e0f")
    assert second.byte_range == (802 + 33091, 28106)
    assert second.key == first.key


def test_parse_media_playlist_byterange_continuation():
    playlist = parse_media_playlist(
        """#EXTM3U
#EXT-X-MEDIA-SEQUENCE:3
#EXTINF:1,
#EXT-X-BYTERANGE:100@0
file.mp4
#EXTINF:1,
#EXT-X-BYTERANGE:50
file.mp4
#EXTINF:1,
#EXT-X-BYTERANGE:25@500
file.mp4
#EXTINF:1,
#EXT-X-BYTERANGE:10
file.mp4
#EXT-X-ENDLIST
""",
    )

    assert [segment.byte_range for segment in playlist.segments] == [
        (0, 100),
        (100, 50),
        (500, 25),
        (525, 10),
    ]


def test_parse_media_playlist_clears_key():
    playlist = parse_media_playlist(
        """#EXTM3U
#EXT-X-KEY:METHOD=AES-128,URI="key.bin"
#EXTINF:1,
#EXT-X-MAP:URI="init.mp4"
encrypted.mp4
#EXT-X-KEY:METHOD=NONE
#EXTINF:1,
plain.mp4
#EXT-X-ENDLIST
""",
    )

    assert playlist.segments[0].key is not None
    assert playlist.segments[0].key.iv is None
    assert playlist.segments[1].key is None


@pytest.mark.parametrize(
    "playlist",
    [
        '#EXTM3U\n#EXT-X-KEY:METHOD=SAMPLE-AES,URI="key.bin"\n#EXTINF:1,\nsegment.mp4\n',
        "#EXTM3U\n#EXT-X-KEY:METHOD=AES-128\n#EXTINF:1,\nsegment.mp4\n",
        '#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="key.bin",IV=0xzz\n#EXTINF:1,\nsegment.mp4\n',
        "#EXTM3U\n#EXTINF:1,\n#EXT-X-BYTERANGE:not-a-range\nsegment.mp4\n",
        "#EXTM3U\n#EXT-X-ENDLIST\n",
    ],
)
def test_parse_media_playlist_errors(playlist):
    with pytest.raises((PodMeApiHlsError, PodMeApiStreamUrlNotFoundError)):
        parse_media_playlist(playlist)


def test_decrypt_segment_round_trip():
    key = bytes(range(16))
    iv = bytes(reversed(range(16)))
    plaintext = b"some fragmented mp4 audio bytes" * 4

    ciphertext = encrypt_aes128(plaintext, key, iv)

    assert decrypt_segment(ciphertext, key, iv) == plaintext


def test_decrypt_segment_invalid_padding():
    key = bytes(range(16))
    iv = bytes(16)
    # Encrypt a block whose last byte is zero so that the decrypted data ends
    # with an invalid PKCS7 padding byte.
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    ciphertext = encryptor.update(bytes(15) + b"\x00") + encryptor.finalize()

    with pytest.raises(PodMeApiHlsError, match="padding"):
        decrypt_segment(ciphertext, key, iv)


@pytest.mark.parametrize(
    ("data", "key", "iv"),
    [
        (b"x" * 16, b"short", bytes(16)),
        (b"x" * 16, bytes(16), b"short"),
        (b"not-aligned", bytes(16), bytes(16)),
        (b"", bytes(16), bytes(16)),
    ],
)
def test_decrypt_segment_errors(data, key, iv):
    with pytest.raises(PodMeApiHlsError):
        decrypt_segment(data, key, iv)


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200):
        self.body = body
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    def raise_for_status(self):
        return None

    async def read(self):
        return self.body


class FakeSession:
    def __init__(self, body: bytes, status: int = 200):
        self.body = body
        self.status = status
        self.requests: list[tuple[str, dict[str, str]]] = []

    def get(self, url: str, headers: dict[str, str] | None = None):
        self.requests.append((url, dict(headers or {})))
        return FakeResponse(self.body, self.status)


async def test_fetch_bytes_range():
    session = FakeSession(b"0123456789abcdef")

    data = await fetch_bytes(session, "https://cdn.example.com/file.mp4", byte_range=(4, 4))

    assert data == b"4567"
    assert session.requests[0][1]["Range"] == "bytes=4-7"


async def test_fetch_bytes_range_ignored_by_server():
    session = FakeSession(b"0123456789abcdef")

    data = await fetch_bytes(session, "https://cdn.example.com/file.mp4", byte_range=(10, 3))

    assert data == b"abc"


async def test_fetch_bytes_partial_content():
    session = FakeSession(b"4567", status=206)

    data = await fetch_bytes(session, "https://cdn.example.com/file.mp4", byte_range=(4, 4))

    assert data == b"4567"
