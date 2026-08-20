from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlparse


def _safe_http_url(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text.lower().startswith(("http://", "https://")):
        return None
    return text


def is_open_data_url(value: Any) -> bool:
    candidate = _safe_http_url(value)
    if not candidate:
        return False
    try:
        return (urlparse(candidate).hostname or "").lower() == "opendata.gijon.es"
    except ValueError:
        return False


def is_open_data_event(event: dict[str, Any]) -> bool:
    links = event.get("links") or {}
    source_name = str(event.get("source_name") or "").lower()
    source_url = event.get("source_url") or links.get("source")
    return is_open_data_url(source_url) or ("open data" in source_name and "gij" in source_name)


def corroborating_source(event: dict[str, Any]) -> tuple[str, str] | None:
    """Return the best public corroborating page for a Gijón Open Data event.

    Priority is the specific municipal page first, followed by another official
    event page. The Open Data feed itself is intentionally excluded here and
    remains provenance / last-resort material only.
    """
    links = event.get("links") or {}
    candidates = (
        (links.get("municipal_page"), "Ayuntamiento de Gijón/Xixón — ficha específica del evento"),
        (links.get("official"), "Fuente oficial específica del evento"),
    )
    for value, label in candidates:
        url = _safe_http_url(value)
        if url and not is_open_data_url(url):
            return url, label
    return None


def public_source(
    event: dict[str, Any],
    safe_url: Callable[[Any], str | None],
) -> tuple[str | None, str, bool]:
    """Return ``(url, label, is_last_resort_open_data)`` for public display."""
    links = event.get("links") or {}
    if is_open_data_event(event):
        corroborating = corroborating_source(event)
        if corroborating:
            url, label = corroborating
            return url, label, False
        fallback = safe_url(event.get("source_url") or links.get("source"))
        return fallback, "Open Data — último recurso", bool(fallback)

    official = safe_url(links.get("official"))
    if official:
        return official, str(event.get("source_name") or "Fuente oficial"), False
    source = safe_url(event.get("source_url") or links.get("source"))
    return source, str(event.get("source_name") or "Fuente de datos"), False
