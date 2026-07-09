from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from .config import BASE_URL, GEDS_PATH
from .models import PersonIndex

MAX_PAGES_PER_ORG = 500
PEOPLE_PAGE_SIZE = 25


@dataclass(frozen=True)
class PeoplePage:
    people: tuple[PersonIndex, ...]
    next_url: str | None


def canonical_pagination_url(href: str | None) -> str | None:
    if not href:
        return None
    absolute = urljoin(f"{BASE_URL}{GEDS_PATH}", href)
    parsed = urlsplit(absolute)
    allowed = urlsplit(BASE_URL)
    if parsed.scheme != "https" or parsed.netloc != allowed.netloc:
        return None
    if parsed.path != GEDS_PATH:
        return None
    query = sorted(parse_qsl(parsed.query, keep_blank_values=True))
    if not any(key == "pgid" and value == "014" for key, value in query):
        return None
    return urlunsplit(("https", allowed.netloc, GEDS_PATH, urlencode(query), ""))


def ajax_pagination_url(
    page: int,
    total: int,
    signed_filter: str,
    sort_type: str = "",
) -> str:
    query = urlencode(
        {
            "pgid": "153",
            "p1": str(page),
            "p2": signed_filter,
            "p3": "1",
            "p4": sort_type,
            "total": str(total),
        }
    )
    return urlunsplit(("https", urlsplit(BASE_URL).netloc, GEDS_PATH, query, ""))


def parse_ajax_pagination_url(url: str) -> dict[str, str] | None:
    parsed = urlsplit(url)
    allowed = urlsplit(BASE_URL)
    if (
        parsed.scheme != "https"
        or parsed.netloc != allowed.netloc
        or parsed.path != GEDS_PATH
    ):
        return None

    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    if len(pairs) != 6 or len({key for key, _ in pairs}) != 6:
        return None
    query = dict(pairs)
    if set(query) != {"pgid", "p1", "p2", "p3", "p4", "total"}:
        return None
    if query["pgid"] != "153" or query["p3"] != "1" or not query["p2"]:
        return None
    try:
        page = int(query["p1"])
        total = int(query["total"])
    except ValueError:
        return None
    if page < 2 or total < 1:
        return None
    return query
