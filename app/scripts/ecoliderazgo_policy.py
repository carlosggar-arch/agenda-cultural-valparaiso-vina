from __future__ import annotations

import re
import unicodedata

SOURCE_ID = "ecoliderazgo"
DEFAULT_ORIGIN_SCOPE = ("Viña del Mar", "Valparaíso")
DEFAULT_ORIGIN_LABEL = "Viña del Mar / Valparaíso"

_LOCAL_ORIGIN_PATTERNS = (
    re.compile(r"\b(?:salida|salimos|partida|partimos)\b.{0,80}\b(?:desde|en)\s+(?:el\s+)?(?:centro\s+de\s+)?(?:vina(?:\s+del\s+mar)?|valparaiso)\b", re.I),
    re.compile(r"\b(?:punto\s+de\s+encuentro|encuentro|nos\s+juntamos)\b.{0,50}\b(?:en\s+|:\s*)?(?:vina(?:\s+del\s+mar)?|valparaiso)\b", re.I),
    re.compile(r"\b(?:bus|transporte)\b.{0,50}\bdesde\s+(?:vina(?:\s+del\s+mar)?|valparaiso)\b", re.I),
)
_EXPLICIT_DEPARTURE_PATTERNS = (
    re.compile(r"\b(?:salida|salimos|partida|partimos)\b.{0,80}\b(?:desde|en)\b", re.I),
    re.compile(r"\b(?:punto\s+de\s+encuentro|encuentro|nos\s+juntamos)\b", re.I),
    re.compile(r"\b(?:bus|transporte)\b.{0,50}\bdesde\b", re.I),
)


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", text.casefold()).strip()


def departure_policy(text: object) -> dict:
    """Apply the source-specific EcoLiderazgo departure rule.

    When an EcoLiderazgo excursion does not state a departure point, its normal
    departure scope is Viña del Mar / Valparaíso. Explicit departure text always
    overrides that source default. Destination mentions never qualify an
    explicitly non-local departure.
    """
    value = norm(text)
    explicit_local = any(pattern.search(value) for pattern in _LOCAL_ORIGIN_PATTERNS)
    explicit_departure = any(pattern.search(value) for pattern in _EXPLICIT_DEPARTURE_PATTERNS)

    if explicit_local:
        return {
            "eligible": True,
            "departure_origin_scope": DEFAULT_ORIGIN_LABEL,
            "departure_origin_mode": "explicit_local",
            "departure_origin_confidence": "explicit",
            "departure_origin_rule": "explicit_source_text",
        }

    if explicit_departure:
        return {
            "eligible": False,
            "departure_origin_scope": None,
            "departure_origin_mode": "explicit_other",
            "departure_origin_confidence": "explicit",
            "departure_origin_rule": "explicit_source_text_overrides_default",
        }

    return {
        "eligible": True,
        "departure_origin_scope": DEFAULT_ORIGIN_LABEL,
        "departure_origin_mode": "source_default",
        "departure_origin_confidence": "source_default",
        "departure_origin_rule": "user_confirmed_ecoliderazgo_default",
    }


def annotate_editorial(editorial: dict | None, text: object) -> dict:
    result = dict(editorial or {})
    policy = departure_policy(text)
    result.update({
        "departure_origin_scope": policy["departure_origin_scope"],
        "departure_origin_mode": policy["departure_origin_mode"],
        "departure_origin_confidence": policy["departure_origin_confidence"],
        "departure_origin_rule": policy["departure_origin_rule"],
    })
    return result
