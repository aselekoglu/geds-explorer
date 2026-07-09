import json
from unittest.mock import patch
from urllib.parse import parse_qsl

from geds_crawler.fetcher import PoliteFetcher


class _Headers:
    def get_content_charset(self):
        return "utf-8"


class _Response:
    headers = _Headers()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps({"searchResults": "<ol><li>page two</li></ol>"}).encode()


def test_ajax_pagination_url_is_sent_as_form_post_and_returns_result_fragment():
    url = (
        "https://geds-sage.gc.ca/en/GEDS?"
        "pgid=153&p1=2&p2=signed-filter-token&p3=1&p4=&total=116"
    )
    with patch("urllib.request.urlopen", return_value=_Response()) as urlopen:
        result = PoliteFetcher(rate_limit_seconds=0).fetch_text(url)

    request = urlopen.call_args.args[0]
    assert request.full_url == "https://geds-sage.gc.ca/en/GEDS?pgid=153"
    assert dict(parse_qsl(request.data.decode(), keep_blank_values=True)) == {
        "p1": "2",
        "p2": "signed-filter-token",
        "p3": "1",
        "p4": "",
    }
    assert result == "<ol><li>page two</li></ol>"
