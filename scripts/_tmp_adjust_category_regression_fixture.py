from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"fixture anchor missing in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace(
    ROOT / "app/scripts/test_public_category_regressions.py",
    '            "Matriarcas: Poesía, Papel y Tinta",\n            "teatro",\n            description=',
    '            \'Teatro "Matriarcas: Poesía, Papel y Tinta"\',\n            "teatro",\n            tags=["Teatro"],\n            description=',
)
replace(
    ROOT / "app/public-category-regressions.test.mjs",
    '  "Matriarcas: Poesía, Papel y Tinta",\n  "teatro",\n  { description:',
    '  \'Teatro "Matriarcas: Poesía, Papel y Tinta"\',\n  "teatro",\n  { tags: ["Teatro"], description:',
)
print("MATRIARCAS_REGRESSION_FIXTURE_ALIGNED")
