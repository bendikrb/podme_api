from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
import random
import string

from podme_api.auth.models import PodMeBffData


class FormParser(HTMLParser):
    """A custom HTML parser for extracting BFF data from HTML content.

    This parser is designed to find and extract data from a specific div
    element with the id "bffData" in the HTML content.

    Attributes:
        current_script (str): Tracks the current script being parsed.
        bff_data (str): Stores the extracted BFF data.

    """

    def __init__(self):
        super().__init__()
        self.current_script = None
        self.bff_data = None

    def handle_starttag(self, tag, attrs):
        """Handle the start tag of an HTML element.

        Args:
            tag (str): The name of the HTML tag.
            attrs (list): A list of (attribute, value) pairs.

        """
        if tag == "div":
            attr_dict = dict(attrs)
            if "id" in attr_dict and attr_dict["id"] == "bffData":
                self.current_script = "bff_data"

    def handle_data(self, data):
        """Handle the data within an HTML element.

        Args:
            data (str): The data content of the HTML element.

        """
        if self.current_script == "bff_data":
            self.bff_data = data.strip()

    def handle_endtag(self, tag):
        """Handle the end tag of an HTML element.

        Args:
            tag (str): The name of the HTML tag.

        """
        if tag == "div":
            self.current_script = None


def parse_schibsted_auth_html(html_content) -> PodMeBffData:
    """Parse Schibsted authentication HTML content and extract BFF data.

    Args:
        html_content (str): The HTML content to parse.

    """
    parser = FormParser()
    parser.feed(html_content)
    return PodMeBffData.from_json(parser.bff_data)


def get_uuid(n: int = 23) -> str:
    """Generate a random UUID-like string.

    Args:
        n (int): The length of the UUID string to generate. Defaults to 23.

    """
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))  # noqa: S311


def get_now_iso() -> str:
    """Get the current UTC time in ISO 8601 format with millisecond precision."""
    return datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
