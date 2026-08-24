from __future__ import annotations

import unicodedata
from collections import Counter
from collections.abc import Iterable

# Human-readable titles can legitimately differ in Unicode typography between
# source data and rendered HTML. Keep the equivalence intentionally narrow:
# compatibility Unicode, whitespace and dash glyphs only. Words, accents,
# punctuation other than dashes, and letter case remain significant.
_DASH_TRANSLATION = str.maketrans({
    "\u2010": "-",  # hyphen
    "\u2011": "-",  # non-breaking hyphen
    "\u2012": "-",  # figure dash
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2015": "-",  # horizontal bar
    "\u2212": "-",  # minus sign
    "\ufe58": "-",  # small em dash
    "\ufe63": "-",  # small hyphen-minus
    "\uff0d": "-",  # fullwidth hyphen-minus
})

IDENTITY_CONTRACT = "unicode-dash-whitespace-v1"


def canonical_title(value: object) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).translate(_DASH_TRANSLATION)
    return " ".join(normalized.split()).strip()


def evaluate_title_contract(
    rendered_titles: Iterable[object],
    *,
    expected_titles: Iterable[object] = (),
    preserved_titles: Iterable[object] = (),
    forbidden_titles: Iterable[object] = (),
) -> dict[str, list[str]]:
    rendered = [canonical_title(title) for title in rendered_titles]
    counts = Counter(title for title in rendered if title)

    expected = [str(title) for title in expected_titles]
    preserved = [str(title) for title in preserved_titles]
    forbidden = [str(title) for title in forbidden_titles]
    required = expected + preserved

    required_keys = [canonical_title(title) for title in required]
    required_key_counts = Counter(required_keys)
    contract_collisions = [
        title
        for title, key in zip(required, required_keys, strict=True)
        if key and required_key_counts[key] > 1
    ]

    missing = [title for title in expected if counts[canonical_title(title)] == 0]
    preserved_missing = [title for title in preserved if counts[canonical_title(title)] == 0]
    duplicates = [title for title in required if counts[canonical_title(title)] > 1]
    forbidden_present = [title for title in forbidden if counts[canonical_title(title)] > 0]

    return {
        "missing": missing,
        "preserved_missing": preserved_missing,
        "duplicates": duplicates,
        "forbidden": forbidden_present,
        "contract_collisions": contract_collisions,
    }
