from __future__ import annotations

import json
import tempfile
from pathlib import Path

from source_refresh_candidate import baseline_is_current, evaluate, snapshot


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def _root(valpo: list[dict], gijon: list[dict]) -> tempfile.TemporaryDirectory[str]:
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    _write(root / "agenda_web.json", valpo)
    _write(root / "app/data/gijon/agenda_web.json", gijon)
    tmp.root = root  # type: ignore[attr-defined]
    return tmp


def test_no_change_is_noop() -> None:
    tmp = _root([{"id": "v1"}], [{"id": "g1"}])
    try:
        root = Path(tmp.name)
        before = snapshot(root)
        after = snapshot(root)
        decision = evaluate(before, after, {"valparaiso"})
        assert decision["status"] == "no_change"
        assert decision["changed_cities"] == []
    finally:
        tmp.cleanup()


def test_allowed_city_change_builds_candidate() -> None:
    tmp = _root([{"id": "v1"}], [{"id": "g1"}])
    try:
        root = Path(tmp.name)
        before = snapshot(root)
        _write(root / "agenda_web.json", [{"id": "v1"}, {"id": "v2"}])
        after = snapshot(root)
        decision = evaluate(before, after, {"valparaiso"})
        assert decision["status"] == "candidate"
        assert decision["changed_cities"] == ["valparaiso"]
        assert decision["before"]["gijon"]["sha256"] == decision["after"]["gijon"]["sha256"]
    finally:
        tmp.cleanup()


def test_untouched_city_change_fails_closed() -> None:
    tmp = _root([{"id": "v1"}], [{"id": "g1"}])
    try:
        root = Path(tmp.name)
        before = snapshot(root)
        _write(root / "app/data/gijon/agenda_web.json", [{"id": "g1"}, {"id": "g2"}])
        after = snapshot(root)
        try:
            evaluate(before, after, {"valparaiso"})
        except SystemExit as exc:
            assert "SOURCE_REFRESH_UNTOUCHED_CITY_CHANGED=gijon" in str(exc)
        else:
            raise AssertionError("untouched-city mutation must fail")
    finally:
        tmp.cleanup()


def test_baseline_must_match_exact_sha() -> None:
    assert baseline_is_current("abc", "abc") is True
    assert baseline_is_current("abc", "def") is False
    assert baseline_is_current("", "") is False


def test_future_event_is_preserved_as_data() -> None:
    event = {"id": "future", "date": "2099-09-05", "title": "Future event"}
    tmp = _root([event], [{"id": "g1"}])
    try:
        root = Path(tmp.name)
        snap = snapshot(root)
        assert snap["valparaiso"]["events"] == 1
        assert json.loads((root / "agenda_web.json").read_text(encoding="utf-8"))[0] == event
    finally:
        tmp.cleanup()


if __name__ == "__main__":
    test_no_change_is_noop()
    test_allowed_city_change_builds_candidate()
    test_untouched_city_change_fails_closed()
    test_baseline_must_match_exact_sha()
    test_future_event_is_preserved_as_data()
    print("SOURCE_REFRESH_CANDIDATE_TESTS_OK")
