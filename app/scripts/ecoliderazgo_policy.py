from __future__ import annotations

import re
import unicodedata

SOURCE_ID = "ecoliderazgo"
DEFAULT_ORIGIN_SCOPE = ("Viña del Mar", "Valparaíso")
DEFAULT_ORIGIN_LABEL = "Viña del Mar / Valparaíso"

_LOCAL_TOKENS = (
    "vina del mar",
    "vina",
    "valparaiso",
)
_DEPARTURE_MARKERS = (
    "salida desde",
    "salida en",
    "salimos desde",
    "partimos desde",
    "punto de encuentro",
    "encuentro en",
    "nos juntamos en",
    "bus desde",
    "transporte desde",
)


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", text.casefold()).strip()


def departure_policy(text: object) -> dict:
    """Apply the source-specific EcoLiderazgo departure rule.

    When an EcoLiderazgo excursion does not state a departure point, its normal
    departure scope is Viña del Mar / Valparaíso. Explicit departure text always
    overrides that source default.
    """
    value = norm(text)
    explicit_marker = next((marker for marker in _DEPARTURE_MARKERS if marker in value), None)
    explicit_local = explicit_marker is not None and any(token in value for token in _LOCAL_TOKENS)

    if explicit_local:
        return {
            "eligible": True,
            "departure_origin_scope": DEFAULT_ORIGIN_LABEL,
            "departure_origin_mode": "explicit_local",
            "departure_origin_confidence": "explicit",
            "departure_origin_rule": "explicit_source_text",
        }

    if explicit_marker is not None:
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
