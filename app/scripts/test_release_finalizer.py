from __future__ import annotations

from release_finalizer import (
    FINALIZER_ALLOWED_FILES,
    FINALIZER_MARKER,
    GENERATED_RELEASE_FILES,
    GENERATED_RELEASE_FRAGMENTS,
    build_provenance,
    release_number_from_text,
    render_release_version,
    replace_index_release_keys,
    validate_generated_change_sets,
)


def main() -> None:
    assert release_number_from_text("const RELEASE = 225;") == 225
    rendered = render_release_version(226, "a" * 40)
    assert "const RELEASE = 226;" in rendered
    assert "source aaaaaaaaaaaa" in rendered
    shell = '<script type="module" src="./app.js?v=225"></script>\n<script type="module" src="./map-navigation-enhancer.js?v=225"></script>\n'
    updated = replace_index_release_keys(shell, 226)
    assert './app.js?v=226' in updated and './map-navigation-enhancer.js?v=226' in updated
    payload = build_provenance(release=226, base_sha="b" * 40, source_sha="c" * 40, source_pr=446)
    assert payload["release"] == 226
    assert payload["base_sha"] == "b" * 40
    assert payload["source_sha"] == "c" * 40
    assert payload["source_pr"] == 446
    assert payload["generator"] == "app/scripts/release_finalizer.py"
    assert payload["generated_artifacts"] == sorted(GENERATED_RELEASE_FILES)
    assert payload["generated_fragments"] == list(GENERATED_RELEASE_FRAGMENTS)
    assert FINALIZER_MARKER == "[release-finalized]"

    generated_sequence = [
        {"app/release-version.js"},
        {"app/index.html"},
        {"app/data/release-provenance.json"},
        {"app/data/release-bundle.json"},
    ]
    combined = validate_generated_change_sets(generated_sequence)
    assert combined <= FINALIZER_ALLOWED_FILES
    assert {
        "app/release-version.js",
        "app/index.html",
        "app/data/release-provenance.json",
        "app/data/release-bundle.json",
    } <= combined
    try:
        validate_generated_change_sets(generated_sequence + [{"app/app.js"}])
    except SystemExit as exc:
        assert "FINALIZER_CHANGED_SOURCE_FILES" in str(exc)
    else:
        raise AssertionError("source changes inside finalization sequence must fail closed")

    try:
        replace_index_release_keys('<script type="module" src="./app.js?v=225"></script>', 226)
    except ValueError:
        pass
    else:
        raise AssertionError("missing canonical module release key must fail closed")
    print("RELEASE_FINALIZER_TESTS_OK")


if __name__ == "__main__":
    main()
