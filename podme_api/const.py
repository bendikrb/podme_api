"""podme_api constants."""

import logging

PODME_AUTH_USER_AGENT = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0"
PODME_API_URL = "https://api.podme.com/web/api/v2"
PODME_BASE_URL = "https://podme.com"
PODME_AUTH_BASE_URL = "https://payment.schibsted.no"
PODME_AUTH_RETURN_URL = f"{PODME_BASE_URL}/no/oppdag"

TIMEOUT = 10

LOGGER = logging.getLogger(__package__)
