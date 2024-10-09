from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
import random
import string

from podme_api.auth.models import PodMeBffData


class FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current_script = None
        self.bff_data = None

    def handle_starttag(self, tag, attrs):
        if tag == "div":
            attr_dict = dict(attrs)
            if "id" in attr_dict and attr_dict["id"] == "bffData":
                self.current_script = "bff_data"

    def handle_data(self, data):
        if self.current_script == "bff_data":
            self.bff_data = data.strip()

    def handle_endtag(self, tag):
        if tag == "div":
            self.current_script = None


def parse_schibsted_auth_html(html_content) -> PodMeBffData:
    parser = FormParser()
    parser.feed(html_content)
    return PodMeBffData.from_json(parser.bff_data)


def get_uuid(n: int = 23) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))  # noqa: S311


def get_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
