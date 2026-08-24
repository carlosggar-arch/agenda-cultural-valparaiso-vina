from __future__ import annotations

from production_title_identity import canonical_title, evaluate_title_contract


def test_dash_and_whitespace_equivalence() -> None:
    expected = "Concierto piano a la luz de las velas — Edición infantil"
    rendered = "  Concierto\u00a0piano a la luz de las velas – Edición infantil  "
    assert canonical_title(expected) == canonical_title(rendered)


def test_semantic_text_remains_strict() -> None:
    assert canonical_title("Canciones inolvidables") != canonical_title("Grandes bandas sonoras")
    assert canonical_title("Edición infantil") != canonical_title("edición infantil")


def test_contract_accepts_typographic_variant_and_keeps_one_to_one_cardinality() -> None:
    result = evaluate_title_contract(
        [
            "Piano a la luz de las velas – Grandes bandas sonoras",
            "Piano a la luz de las velas — Tributo a ABBA, Queen, The Beatles y Mecano",
            "Piano a la luz de las velas — Canciones inolvidables",
            "Concierto piano a la luz de las velas – Edición infantil",
        ],
        expected_titles=[
            "Piano a la luz de las velas — Grandes bandas sonoras",
            "Piano a la luz de las velas — Tributo a ABBA, Queen, The Beatles y Mecano",
            "Piano a la luz de las velas — Canciones inolvidables",
        ],
        preserved_titles=["Concierto piano a la luz de las velas — Edición infantil"],
        forbidden_titles=["Concierto piano a la luz de las velas"],
    )
    assert all(not values for values in result.values()), result


def test_duplicate_required_title_fails_cardinality() -> None:
    title = "Piano a la luz de las velas — Grandes bandas sonoras"
    result = evaluate_title_contract(
        [title, title.replace("—", "–")],
        expected_titles=[title],
    )
    assert result["duplicates"] == [title]


def test_forbidden_parent_is_detected() -> None:
    parent = "Concierto piano a la luz de las velas"
    result = evaluate_title_contract([parent], forbidden_titles=[parent])
    assert result["forbidden"] == [parent]


if __name__ == "__main__":
    test_dash_and_whitespace_equivalence()
    test_semantic_text_remains_strict()
    test_contract_accepts_typographic_variant_and_keeps_one_to_one_cardinality()
    test_duplicate_required_title_fails_cardinality()
    test_forbidden_parent_is_detected()
    print("PRODUCTION_TITLE_IDENTITY_TESTS_OK cases=5 identity=unicode-dash-whitespace-v1 cardinality=one-to-one")
