"""podme_api constants."""

import logging

from podme_api.models import PodMeRegion

PODME_AUTH_USER_AGENT = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0"
PODME_API_USER_AGENT = "Podme android app/6.29.3 (Linux;Android 15) AndroidXMedia3/1.5.1"
PODME_API_BASE_URL = "https://api.podme.com"
PODME_BASE_URL = "https://podme.com"

PODME_AUTH_BASE_URL = {
    PodMeRegion.NO: "https://payment.schibsted.no",
    PodMeRegion.SE: "https://login.schibsted.com",
    PodMeRegion.FI: "https://login.schibsted.fi",
    PodMeRegion.DK: "https://login.schibsted.dk",
}
PODME_AUTH_CLIENT_ID = {
    PodMeRegion.NO: "62557b19f552881812b7431c",
    PodMeRegion.SE: "66fd141b3f97a8558ace8ab9",  # TODO: Check
    PodMeRegion.FI: "62557b19f552881812b7431c",  # TODO: Check
    PodMeRegion.DK: "62557b19f552881812b7431c",  # TODO: Check
}

DEFAULT_REQUEST_TIMEOUT = 15

LOGGER = logging.getLogger(__package__)
