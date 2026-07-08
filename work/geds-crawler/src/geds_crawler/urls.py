from __future__ import annotations

import base64
from urllib.parse import parse_qs, quote, unquote, urlencode, urljoin, urlparse

from .config import BASE_URL, GEDS_PATH
from .models import ParsedLink


def canonical_dn(value: str) -> str:
    """Return a decoded DN for dedupe, accepting raw, URL-encoded, or base64 DN values."""
    if not value:
        return ""

    decoded = unquote(value).strip()
    if "=" in decoded and "," in decoded:
        return decoded

    try:
        padded = decoded + ("=" * (-len(decoded) % 4))
        candidate = base64.b64decode(padded, validate=False).decode("utf-8").strip()
    except Exception:
        return decoded

    return candidate if candidate else decoded


def encode_dn(dn: str) -> str:
    encoded = base64.b64encode(dn.encode("utf-8")).decode("ascii")
    return quote(encoded, safe="")


def geds_url(pgid: str, dn: str | None = None) -> str:
    if dn is None:
        return f"{BASE_URL}{GEDS_PATH}?{urlencode({'pgid': pgid})}"
    return f"{BASE_URL}{GEDS_PATH}?pgid={quote(pgid, safe='')}&dn={encode_dn(canonical_dn(dn))}"


def normalize_url(href: str) -> str:
    if href.startswith("?"):
        return f"{BASE_URL}{GEDS_PATH}{href}"
    return urljoin(BASE_URL, href)


def parse_geds_link(href: str | None) -> ParsedLink | None:
    if not href:
        return None

    url = normalize_url(href)
    parsed = urlparse(url)
    if parsed.netloc != urlparse(BASE_URL).netloc or not parsed.path.endswith("/GEDS"):
        return None

    query = parse_qs(parsed.query)
    pgid = query.get("pgid", [""])[0]
    dn = query.get("dn", [""])[0]
    if not pgid or not dn:
        return None

    return ParsedLink(pgid=pgid, dn=canonical_dn(dn), url=url)
