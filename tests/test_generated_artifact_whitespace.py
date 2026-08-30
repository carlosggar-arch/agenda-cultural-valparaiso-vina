import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from generate_event_pages import normalize_generated_html  # noqa: E402


def test_generated_html_removes_whitespace_only_interpolation_lines() -> None:
    generated = normalize_generated_html("<h1>Evento</h1>\n        \n<p>Detalle</p>  \n")

    assert generated == "<h1>Evento</h1>\n\n<p>Detalle</p>\n"


def test_ics_artifacts_have_explicit_crlf_git_normalization() -> None:
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")

    assert "*.ics text eol=crlf" in attributes.splitlines()
