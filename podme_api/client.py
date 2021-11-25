""" PodMe API """
import datetime
import json
import logging
import math
import re
import urllib
import urllib.parse

import requests
from typing import Callable, Dict, List
from .types import PodMeEpisode, PodMeEpisodeExcerpt, PodMePodcast, PodMeSearchResult, PodMeSubscription
from youtube_dl import YoutubeDL
from youtube_dl.utils import YoutubeDLError
from .const import *
from .exceptions import AccessDeniedError

_LOGGER = logging.getLogger(__name__)


class PodMeClient:
    def __init__(self, email: str, password: str, language: str = "no", region: str = "NO"):
        self._email = email
        self._password = password
        self._language = language
        self._region = region
        self._oauth_token = None
        self._refresh_token = None
        self._token_expiration = None
        self._id_token = None

    def login(self):
        self._get_oauth_token()

    def _get_oauth_token(self) -> None:
        """Get a new auth token from the server."""

        if self._token_expiration is not None and datetime.datetime.now() < self._token_expiration:
            _LOGGER.debug('Old token is still valid. Not getting a new one.')
            return

        oauth_session = requests.Session()

        response = oauth_session.get(
            f'{PODME_AUTH_TOKEN_URL}/oauth2/v2.0/authorize',
            params={
                "ui_locales": self._language,
                "client_id": PODME_AUTH_CLIENT_ID,
                "response_type": "token id_token",
                "redirect_uri": PODME_AUTH_REDIRECT_URI,
                "scope": "openid https://reacthello.onmicrosoft.com/reacthelloapi/read",
            }, headers={
                "User-Agent": PODME_AUTH_USER_AGENT,
            })
        response.raise_for_status()
        regex = r"var SETTINGS = ([^\n]*);"
        matches = re.findall(regex, response.content.decode('utf-8'), re.MULTILINE)
        auth_settings = json.loads(matches[0])
        auth_hosts = auth_settings.get('hosts')
        auth_params = {
            "tx": auth_settings.get('transId'),
            "p": auth_hosts.get('policy'),
        }

        authorization = oauth_session.post(
            f'{PODME_AUTH_TOKEN_URL}/SelfAsserted',
            data={
                "request_type": "RESPONSE",
                "logonIdentifier": self._email,
                "password": self._password,
            },
            params=auth_params,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-CSRF-TOKEN": auth_settings.get('csrf'),
            }
        )
        authorization.raise_for_status()

        redirect = oauth_session.get(
            f'{PODME_AUTH_TOKEN_URL}/api/CombinedSigninAndSignup/confirmed',
            params=dict(
                auth_params,
                **{
                    "csrf_token": auth_settings.get('csrf'),
                }))
        redirect.raise_for_status()
        fragment = urllib.parse.urlparse(redirect.url).fragment
        token = urllib.parse.parse_qs(fragment)

        if 'error' in token:
            raise AccessDeniedError(token)

        self._oauth_token = token.get('access_token')[0]
        self._id_token = token.get('id_token')[0]
        expiration_time = int(token.get('expires_in')[0])
        self._token_expiration = datetime.datetime.now() + datetime.timedelta(
            seconds=expiration_time
        )
        _LOGGER.debug(
            "got new token %s with expiration date %s",
            self._oauth_token,
            self._token_expiration,
        )

    @property
    def request_header(self) -> dict[str, str]:
        """Generate a header for HTTP requests to the server."""
        self._get_oauth_token()
        headers = {
            "Accept": "application/json",
            "Authorization": "Bearer {}".format(self._oauth_token),
            "X-Region": self._region,
        }
        return headers

    def _get_pages(self, url, get_by_oldest=False, get_pages=None, page_size=None, params=None):
        if get_pages is None:
            get_pages = math.inf
        if page_size is None:
            page_size = 50
        if params is None:
            params = {}
        data = []
        new_results = True
        page = 0
        while new_results and page < get_pages:
            try:
                response = requests.get(
                    url,
                    params={
                        **{
                            "pageSize": page_size,
                            "page": page,
                            "getByOldest": get_by_oldest,
                        },
                        **params,
                    }, headers=self.request_header
                ).json()
                new_results = response
                data.extend(response)
                page += 1
            except json.JSONDecodeError:
                new_results = []

        return data

    @staticmethod
    def _download_episode_hook(d):
        if d['status'] == 'finished':
            _LOGGER.info('Done downloading, now converting ...')

    def download_episode(self, path, url, on_finished: Callable[[Dict], None] = None):
        def _progress_hook(d):
            self._download_episode_hook(d)
            if on_finished is not None:
                on_finished(d)

        ydl_opts = {
            'logger': _LOGGER,
            'progress_hooks': [_progress_hook],
            'outtmpl': path
        }
        with YoutubeDL(ydl_opts) as ydl:
            try:
                ydl.download([url])
                return True
            except YoutubeDLError:
                _LOGGER.fatal(f"youtube-dl failed to harvest from {url} to {path}")
                return False

    def get_user_subscription(self) -> PodMeSubscription:
        subscription = requests.get(
            PODME_API_URL.format(endpoint="subscription"),
            headers=self.request_header,
        ).json()
        
        return subscription

    def get_user_podcasts(self) -> List[PodMeEpisodeExcerpt]:
        podcasts = self._get_pages(
            PODME_API_URL.format(endpoint="/podcast/userpodcasts"),
        )

        return podcasts

    def get_popular_podcasts(self) -> List[PodMeEpisodeExcerpt]:
        podcasts = self._get_pages(
            PODME_API_URL.format(endpoint="/podcast/popular"),
            params={
                "podcastType": 2,
                "category": "",
            }
        )

        return podcasts

    def get_podcast_info(self, podcast_slug: str) -> PodMePodcast:
        data = requests.get(
            PODME_API_URL.format(endpoint=f"/podcast/slug/{podcast_slug}"),
            headers=self.request_header,
        ).json()

        return data

    def get_episode_info(self, episode_id: int) -> PodMeEpisode:
        data = requests.get(
            PODME_API_URL.format(endpoint=f"/episode/{episode_id}"),
            headers=self.request_header,
        ).json()

        return data

    def search_podcast(self, search: str) -> List[PodMeSearchResult]:
        podcasts = requests.get(
            PODME_API_URL.format(endpoint="/podcast/search"), params={
                "searchText": search,
            },
            headers=self.request_header,
        ).json()
        return podcasts

    def get_episode_list(self, podcast_slug: str) -> List[PodMeEpisodeExcerpt]:
        episodes = self._get_pages(
            PODME_API_URL.format(endpoint=f"/episode/slug/{podcast_slug}"),
            get_by_oldest=True,
        )
        _LOGGER.debug("Retrieved full episode list, containing %s episodes", len(episodes))

        return episodes

    def get_episode_ids(self, slug) -> List[int]:
        episodes = self.get_episode_list(slug)
        return [int(e['id']) for e in episodes]
