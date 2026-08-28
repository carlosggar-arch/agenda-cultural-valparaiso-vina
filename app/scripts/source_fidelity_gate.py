from __future__ import annotations

"""Source fidelity gate.

Protects publication against regressions in already verified event fields.
The gate is intentionally conservative: missing optional data does not block;
only unjustified degradation blocks publication.
"""

from dataclasses import dataclass
from typing import Any


class FidelityError(RuntimeError):
    pass


@dataclass(frozen=True)
class Finding:
    field: str
    reason: str
    severity: str = "block"


def _text(value: Any) -> str:
    return str(value or "").strip()


def check_title(previous: dict[str, Any], current: dict[str, Any]) -> list[Finding]:
    old = _text(previous.get("title"))
    new = _text(current.get("title"))
    if old and new and old != new:
        return [Finding("title", f"verified title changed: {old!r} -> {new!r}")]
    return []


def check_schedule(previous: dict[str, Any], current: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    old = previous.get("schedule") or {}
    new = current.get("schedule") or {}
    if old.get("start") and new.get("start") and old["start"] != new["start"]:
        if current.get("schedule_source") in {"venue_hours", "opening_hours"}:
            findings.append(Finding("schedule", "event time replaced by venue hours"))
    return findings


def check_image(previous: dict[str, Any], current: dict[str, Any]) -> list[Finding]:
    old = previous.get("image") or {}
    new = current.get("image") or {}
    old_url = _text(old.get("url"))
    new_url = _text(new.get("url"))
    bad_markers = ("gravatar", "placeholder", "avatar")
    if old_url and old_url != new_url and any(marker in new_url.lower() for marker in bad_markers):
        return [Finding("image", "official image degraded to generic image")]
    return []


def check_event(previous: dict[str, Any], current: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(check_title(previous, current))
    findings.extend(check_schedule(previous, current))
    findings.extend(check_image(previous, current))
    return findings


def assert_fidelity(previous: dict[str, Any], current: dict[str, Any]) -> None:
    findings = check_event(previous, current)
    if findings:
        details = "; ".join(f"{f.field}: {f.reason}" for f in findings)
        raise FidelityError(details)


if __name__ == "__main__":
    print("SOURCE_FIDELITY_GATE_READY")
