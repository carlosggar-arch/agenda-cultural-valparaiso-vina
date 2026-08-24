from __future__ import annotations

import html
import json
import re
import unicodedata
from difflib import SequenceMatcher
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

SOCIAL_HOSTS = {
    "instagram.com", "www.instagram.com", "facebook.com", "www.facebook.com",
    "m.facebook.com", "linktr.ee", "www.linktr.ee",
}
GENERIC_PATHS = {
    "", "/", "/agenda", "/agenda/", "/cartelera", "/cartelera/",
    "/eventos", "/eventos/", "/actividades", "/actividades/",
}
BAD_IMAGE_TOKENS = ("logo", "icon", "avatar", "placeholder", "default", "favicon", "sprite")


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def fetch(url: str, timeout: int = 20) -> tuple[bool, int | None, str, str | None]:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; AgendaCulturalMaintenance/1.0)",
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-CL,es;q=0.9",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310 - URLs come from curated public dataset
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
            try:
                text = raw.decode(charset, errors="replace")
            except LookupError:
                text = raw.decode("utf-8", errors="replace")
            return True, getattr(response, "status", 200), text, None
    except HTTPError as exc:
        return False, exc.code, "", f"HTTP {exc.code}"
    except (URLError, TimeoutError, OSError) as exc:
        return False, None, "", f"{type(exc).__name__}: {exc}"


def jsonld_objects(value):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from jsonld_objects(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from jsonld_objects(nested)


def extract_event_candidates(markup: str) -> list[dict]:
    events = []
    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        markup,
        flags=re.I | re.S,
    ):
        raw = html.unescape(match.group(1)).strip()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for obj in jsonld_objects(payload):
            raw_type = obj.get("@type")
            types = raw_type if isinstance(raw_type, list) else [raw_type]
            if any(str(value).casefold() == "event" for value in types):
                events.append(obj)
    return events


def date_part(value: object) -> str:
    text = str(value or "").strip()
    match = re.match(r"(\d{4}-\d{2}-\d{2})", text)
    return match.group(1) if match else ""


def title_score(item: dict, candidate: dict) -> float:
    a = norm(item.get("title"))
    b = norm(candidate.get("name"))
    if not a or not b:
        return 0.0
    ratio = SequenceMatcher(None, a, b).ratio()
    if a == b:
        ratio = 1.0
    elif a in b or b in a:
        ratio = max(ratio, 0.86)
    current_day = date_part((item.get("schedule") or {}).get("start"))
    candidate_day = date_part(candidate.get("startDate"))
    if current_day and candidate_day and current_day == candidate_day:
        ratio = min(1.0, ratio + 0.08)
    return ratio


def best_matching_event(item: dict, candidates: list[dict]) -> tuple[dict | None, float]:
    ranked = sorted(((title_score(item, candidate), candidate) for candidate in candidates), key=lambda pair: pair[0], reverse=True)
    if not ranked:
        return None, 0.0
    score, candidate = ranked[0]
    current_day = date_part((item.get("schedule") or {}).get("start"))
    candidate_day = date_part(candidate.get("startDate"))
    threshold = 0.62 if current_day and candidate_day and current_day == candidate_day else 0.78
    return (candidate, score) if score >= threshold else (None, score)


def event_detail_url(item: dict) -> str | None:
    links = item.get("links") or {}
    candidates = [links.get("official"), links.get("tickets"), links.get("source"), item.get("source_url")]
    seen = set()
    for value in candidates:
        url = str(value or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        try:
            parsed = urlparse(url)
        except ValueError:
            continue
        host = parsed.netloc.casefold()
        if parsed.scheme not in {"http", "https"} or not host or host in SOCIAL_HOSTS:
            continue
        path = (parsed.path or "/").casefold()
        if path in GENERIC_PATHS:
            continue
        return url
    return None


class MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag, attrs) -> None:
        if tag.casefold() != "meta":
            return
        row = {str(k).casefold(): str(v) for k, v in attrs if k and v is not None}
        key = row.get("property") or row.get("name")
        content = row.get("content")
        if key and content:
            self.meta[key.casefold()] = content


def page_meta(markup: str) -> dict[str, str]:
    parser = MetaParser()
    try:
        parser.feed(markup)
    except Exception:
        pass
    return parser.meta


def normalize_official_image_url(value: object, base_url: str | None = None) -> str | None:
    """Normalize source image metadata without guessing from its filename."""
    url = html.unescape(str(value or "")).strip()
    while len(url) >= 2 and url[0] == url[-1] and url[0] in {"'", '"'}:
        url = url[1:-1].strip()
    if not url:
        return None
    if base_url:
        try:
            base = urlparse(str(base_url).strip())
        except ValueError:
            base = None
        if base and base.scheme in {"http", "https"} and base.netloc:
            url = urljoin(str(base_url).strip(), url)
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    low = url.casefold()
    if any(token in low for token in BAD_IMAGE_TOKENS):
        return None
    return url


def image_url_from_candidate(candidate: dict | None, markup: str = "", base_url: str | None = None) -> str | None:
    image = (candidate or {}).get("image")
    if isinstance(image, list):
        image = image[0] if image else None
    if isinstance(image, dict):
        image = image.get("url") or image.get("contentUrl")
    if not image and markup:
        image = page_meta(markup).get("og:image")
    return normalize_official_image_url(image, base_url)


def location_from_candidate(candidate: dict) -> tuple[str | None, str | None]:
    location = candidate.get("location")
    if isinstance(location, list):
        location = location[0] if location else {}
    if not isinstance(location, dict):
        return None, None
    name = str(location.get("name") or "").strip() or None
    address = location.get("address")
    if isinstance(address, dict):
        parts = [
            address.get("streetAddress"),
            address.get("addressLocality"),
            address.get("addressRegion"),
        ]
        address = ", ".join(str(value).strip() for value in parts if value)
    address = str(address or "").strip() or None
    return name, address


def offer_from_candidate(candidate: dict) -> tuple[float | int | None, str | None, bool | None]:
    offers = candidate.get("offers")
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    if not isinstance(offers, dict):
        return None, None, None
    raw = offers.get("price")
    amount = None
    if raw is not None and str(raw).strip() != "":
        try:
            amount_float = float(str(raw).replace(",", "."))
            amount = int(amount_float) if amount_float.is_integer() else amount_float
        except ValueError:
            amount = None
    currency = str(offers.get("priceCurrency") or "").strip() or None
    availability = str(offers.get("availability") or "").casefold()
    sold_out = True if "soldout" in availability or "sold_out" in availability else None
    return amount, currency, sold_out


def event_status(candidate: dict) -> str:
    raw = str(candidate.get("eventStatus") or "").casefold()
    if "cancel" in raw:
        return "cancelled"
    if "postpon" in raw:
        return "postponed"
    if "reschedul" in raw:
        return "rescheduled"
    return "scheduled" if raw else "unknown"
