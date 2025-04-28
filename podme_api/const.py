"""podme_api constants."""

import logging

PODME_AUTH_USER_AGENT = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0"
PODME_API_USER_AGENT = "Podme android app/6.29.3 (Linux;Android 15) AndroidXMedia3/1.5.1"
PODME_API_URL = "https://api.podme.com/mobile/api"
PODME_BASE_URL = "https://podme.com"
PODME_AUTH_BASE_URL = "https://payment.schibsted.no"
PODME_AUTH_RETURN_URL = f"{PODME_BASE_URL}/no/oppdag"

DEFAULT_REQUEST_TIMEOUT = 15

LOGGER = logging.getLogger(__package__)
