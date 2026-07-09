from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from .config import BASE_URL, GEDS_PATH
from .models import PersonIndex

MAX_PAGES_PER_ORG = 500


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
