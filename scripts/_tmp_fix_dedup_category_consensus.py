from __future__ import annotations

import json
from pathlib import Path

ROOT = Path.cwd()


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"PATCH_MARKER_INVALID {label} count={count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_taxonomy() -> None:
    path = ROOT / "shared/public-category-taxonomy.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["rules"]["merged_category_consensus_weight"] = 180
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def patch_identity_core() -> None:
    path = ROOT / "app/event-identity-core.mjs"
    marker = '''function editorialList(event, field, fallback) {
  const values = event?.editorial?.[field];
  return Array.isArray(values) && values.length ? values : fallback ? [fallback] : [];
}

export function areProbableDuplicateEvents(a, b) {
'''
    replacement = '''function editorialList(event, field, fallback) {
  const values = event?.editorial?.[field];
  return Array.isArray(values) && values.length ? values : fallback ? [fallback] : [];
}

function categoryEvidenceRecord(event) {
  const categoryId = String(
    event?.semantics?.primary_domain
      || event?.primary_category?.id
      || event?.categories?.[0]?.id
      || "",
  ).trim();
  if (!categoryId || categoryId === "unclassified") return null;
  const score = Number(event?.semantics?.score || 0);
  return {
    category_id: categoryId,
    confidence: String(event?.semantics?.confidence || "unspecified"),
    score: Number.isFinite(score) ? score : 0,
    event_id: String(event?.id || ""),
    source_id: String(event?.source_id || ""),
  };
}

function categoryEvidenceRecords(event) {
  const existing = event?.editorial?.merged_category_evidence;
  if (Array.isArray(existing) && existing.length) {
    return existing.filter((item) => item && typeof item === "object");
  }
  const record = categoryEvidenceRecord(event);
  return record ? [record] : [];
}

function mergeCategoryEvidence(primary, secondary) {
  const found = new Map();
  for (const item of [...categoryEvidenceRecords(primary), ...categoryEvidenceRecords(secondary)]) {
    const key = [item?.event_id, item?.source_id, item?.category_id].map((value) => String(value || "")).join("|");
    if (!item?.category_id || found.has(key)) continue;
    found.set(key, {
      category_id: String(item.category_id),
      confidence: String(item.confidence || "unspecified"),
      score: Number.isFinite(Number(item.score)) ? Number(item.score) : 0,
      event_id: String(item.event_id || ""),
      source_id: String(item.source_id || ""),
    });
  }
  return [...found.values()];
}

export function areProbableDuplicateEvents(a, b) {
'''
    replace_once(path, marker, replacement, "identity category evidence helpers")

    marker2 = '''  const rule = duplicateRule(primary, secondary);
  const scheduleConflictResolved = sameLocalOccurrenceDate(primary, secondary) && !sameLocalOccurrenceStart(primary, secondary);

  return {
'''
    replacement2 = '''  const rule = duplicateRule(primary, secondary);
  const scheduleConflictResolved = sameLocalOccurrenceDate(primary, secondary) && !sameLocalOccurrenceStart(primary, secondary);
  const mergedCategoryEvidence = mergeCategoryEvidence(primary, secondary);

  return {
'''
    replace_once(path, marker2, replacement2, "identity merged evidence declaration")

    marker3 = '''      merged_duplicate_ids: mergedIds,
      merged_source_names: mergedSourceNames,
      merged_source_urls: mergedSourceUrls,
    },
'''
    replacement3 = '''      merged_duplicate_ids: mergedIds,
      merged_source_names: mergedSourceNames,
      merged_source_urls: mergedSourceUrls,
      merged_category_evidence: mergedCategoryEvidence,
    },
'''
    replace_once(path, marker3, replacement3, "identity merged evidence output")


def patch_js_classifier() -> None:
    path = ROOT / "app/public-category-rules.mjs"
    marker = '''const TAG_CATEGORY_WEIGHT = Number(RULES.tag_category_weight || 0);
const TAG_CATEGORY_ALIASES = RULES.tag_category_aliases || {};
'''
    replacement = '''const TAG_CATEGORY_WEIGHT = Number(RULES.tag_category_weight || 0);
const TAG_CATEGORY_ALIASES = RULES.tag_category_aliases || {};
const MERGED_CATEGORY_CONSENSUS_WEIGHT = Number(RULES.merged_category_consensus_weight || 0);
'''
    replace_once(path, marker, replacement, "js consensus constant")

    marker2 = '''function confidenceForScore(score) {
'''
    insertion = '''function addMergedCategoryConsensusEvidence(scores, evidence, event) {
  if (!MERGED_CATEGORY_CONSENSUS_WEIGHT) return;
  const rawItems = event?.editorial?.merged_category_evidence;
  if (!Array.isArray(rawItems) || rawItems.length < 2) return;

  const items = rawItems
    .map((item) => ({
      category: canonicalPublicCategory(String(item?.category_id || "")),
      confidence: String(item?.confidence || "unspecified"),
      score: Number(item?.score || 0),
    }))
    .filter((item) => item.category && isThematicCategory(item.category.id));
  if (items.length < 2) return;

  const categoryIds = new Set(items.map((item) => item.category.id));
  if (categoryIds.size !== 1) return;
  const hasStrongObservation = items.some((item) => (
    item.confidence === "high"
    || item.confidence === "medium"
    || item.score >= 70
  ));
  if (!hasStrongObservation) return;

  const [categoryId] = categoryIds;
  addEvidence(
    scores,
    evidence,
    categoryId,
    MERGED_CATEGORY_CONSENSUS_WEIGHT,
    "merged_category_consensus",
    `${categoryId}:${items.length}`,
  );
}

function confidenceForScore(score) {
'''
    replace_once(path, marker2, insertion, "js consensus helper")

    marker3 = '''  if (recoveryHint && isThematicCategory(recoveryHint.id)) {
    addEvidence(
      scores,
      evidence,
      recoveryHint.id,
      Number(RULES.recovery_hint_weight || RULES.source_category_weight || 0),
      "recovery_hint",
      String(event?.editorial?.category_recovery_hint || ""),
    );
  }

  // Generic venue/organizer/source-name text is intentionally excluded.
'''
    replacement3 = '''  if (recoveryHint && isThematicCategory(recoveryHint.id)) {
    addEvidence(
      scores,
      evidence,
      recoveryHint.id,
      Number(RULES.recovery_hint_weight || RULES.source_category_weight || 0),
      "recovery_hint",
      String(event?.editorial?.category_recovery_hint || ""),
    );
  }

  // Cross-source reconciliation is allowed to combine descriptions, but that
  // must not erase a category on which the independently normalized duplicate
  // records already agreed. Treat that agreement as structured semantic evidence.
  addMergedCategoryConsensusEvidence(scores, evidence, event);

  // Generic venue/organizer/source-name text is intentionally excluded.
'''
    replace_once(path, marker3, replacement3, "js consensus classifier call")


def patch_python_classifier() -> None:
    path = ROOT / "scripts/public_category_rules.py"
    marker = '''TAG_CATEGORY_WEIGHT = int(RULES.get("tag_category_weight", 0))
TAG_CATEGORY_ALIASES = dict(RULES.get("tag_category_aliases", {}))
'''
    replacement = '''TAG_CATEGORY_WEIGHT = int(RULES.get("tag_category_weight", 0))
TAG_CATEGORY_ALIASES = dict(RULES.get("tag_category_aliases", {}))
MERGED_CATEGORY_CONSENSUS_WEIGHT = int(RULES.get("merged_category_consensus_weight", 0))
'''
    replace_once(path, marker, replacement, "python consensus constant")

    marker2 = '''def _confidence_for_score(score: int) -> str:
'''
    insertion = '''def _add_merged_category_consensus_evidence(
    scores: dict[str, int],
    evidence: list[dict[str, Any]],
    event: dict[str, Any],
) -> None:
    if not MERGED_CATEGORY_CONSENSUS_WEIGHT:
        return
    editorial = event.get("editorial") if isinstance(event.get("editorial"), dict) else {}
    raw_items = editorial.get("merged_category_evidence")
    if not isinstance(raw_items, list) or len(raw_items) < 2:
        return

    items: list[tuple[str, str, int]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        resolved = canonical_public_category(str(item.get("category_id") or ""))
        category_id = resolved.get("id") if resolved else None
        if not is_thematic_category(category_id):
            continue
        try:
            score = int(item.get("score") or 0)
        except (TypeError, ValueError):
            score = 0
        items.append((str(category_id), str(item.get("confidence") or "unspecified"), score))
    if len(items) < 2:
        return

    category_ids = {item[0] for item in items}
    if len(category_ids) != 1:
        return
    has_strong_observation = any(
        confidence in {"high", "medium"} or score >= 70
        for _, confidence, score in items
    )
    if not has_strong_observation:
        return
    category_id = next(iter(category_ids))
    _add_evidence(
        scores,
        evidence,
        category_id,
        MERGED_CATEGORY_CONSENSUS_WEIGHT,
        "merged_category_consensus",
        f"{category_id}:{len(items)}",
    )


def _confidence_for_score(score: int) -> str:
'''
    replace_once(path, marker2, insertion, "python consensus helper")

    marker3 = '''    if recovery_hint and is_thematic_category(recovery_hint.get("id")):
        _add_evidence(
            scores,
            evidence,
            recovery_hint["id"],
            int(RULES.get("recovery_hint_weight", RULES.get("source_category_weight", 0))),
            "recovery_hint",
            (event.get("editorial") or {}).get("category_recovery_hint"),
        )

    # Generic venue/organizer/source-name text is intentionally excluded.
'''
    replacement3 = '''    if recovery_hint and is_thematic_category(recovery_hint.get("id")):
        _add_evidence(
            scores,
            evidence,
            recovery_hint["id"],
            int(RULES.get("recovery_hint_weight", RULES.get("source_category_weight", 0))),
            "recovery_hint",
            (event.get("editorial") or {}).get("category_recovery_hint"),
        )

    # A cross-source merge must preserve independently normalized category
    # agreement as structured evidence instead of letting merged prose erase it.
    _add_merged_category_consensus_evidence(scores, evidence, event)

    # Generic venue/organizer/source-name text is intentionally excluded.
'''
    replace_once(path, marker3, replacement3, "python consensus classifier call")


def patch_js_regressions() -> None:
    path = ROOT / "app/public-category-regressions.test.mjs"
    marker = '''import assert from "node:assert/strict";
import { resolvePublicCategory } from "./public-category-rules.mjs";
'''
    replacement = '''import assert from "node:assert/strict";
import { resolvePublicCategory } from "./public-category-rules.mjs";
import { deduplicateCrossSourceDataset } from "./cross-source-deduplication.mjs";
'''
    replace_once(path, marker, replacement, "js regression import")

    marker2 = '''console.log("PUBLIC_CATEGORY_JS_REGRESSIONS_OK");
'''
    insertion = '''const matriarcasLiteratureDescription = "Matriarcas es una obra sobre Gabriela Mistral, Alfonsina Storni y Juana de Ibarbourou, literatura latinoamericana, poesía, poetas y una histórica conferencia literaria.";
const matriarcasPcdv = {
  ...event("Matriarcas: Poesía, Papel y Tinta", "teatro", {
    description: matriarcasLiteratureDescription,
    venue: "Parque Cultural de Valparaíso",
    city: "Valparaíso",
  }),
  id: "pcdv-matriarcas",
  source_id: "pcdv",
  source_name: "Parque Cultural de Valparaíso",
  source_url: "https://parquecultural.cl/matriarcas",
  schedule: { start: "2026-08-28T19:00:00-04:00", end: "2026-08-28T19:00:00-04:00" },
  public_status: { source_official: true, information_completeness: "complete" },
  semantics: {
    primary_domain: "teatro",
    confidence: "high",
    score: 230,
    source_category: { id: "teatro", label: "Teatro y danza" },
  },
};
const matriarcasPortal = {
  ...event("Matriarcas", "teatro", {
    description: matriarcasLiteratureDescription,
    venue: "Parque Cultural de Valparaíso",
    city: "Valparaíso",
  }),
  id: "portal-matriarcas",
  source_id: "portaltickets_valparaiso",
  source_name: "PortalTickets — Región de Valparaíso",
  source_url: "https://www.portaltickets.cl/evento/matriarcas",
  schedule: { start: "2026-08-28T19:00:00-04:00", end: "2026-08-28T19:00:00-04:00" },
  public_status: { source_official: false, information_completeness: "complete" },
  semantics: {
    primary_domain: "teatro",
    confidence: "low",
    score: 40,
    source_category: { id: "cultura", label: "Cultura" },
  },
};
const matriarcasDeduped = deduplicateCrossSourceDataset({
  events: [matriarcasPcdv, matriarcasPortal],
  counts: { total: 2, events: 2, courses: 0, flexible_offers: 0, programs: 0 },
});
assert.equal(matriarcasDeduped.events.length, 1, "Matriarcas duplicates must reconcile");
assert.equal(matriarcasDeduped.events[0].primary_category?.id, "teatro", "dedup must preserve agreed Teatro classification");
assert.equal(matriarcasDeduped.events[0].editorial?.merged_category_evidence?.length, 2, "dedup must retain both pre-merge category observations");

expectCategory("merged category consensus beats prose-topic drift", {
  ...event("Matriarcas: Poesía, Papel y Tinta", "teatro", {
    description: matriarcasLiteratureDescription,
    venue: "Parque Cultural de Valparaíso",
    city: "Valparaíso",
  }),
  semantics: { source_category: { id: "teatro", label: "Teatro y danza" } },
  editorial: {
    merged_category_evidence: [
      { category_id: "teatro", confidence: "high", score: 230, event_id: "a", source_id: "pcdv" },
      { category_id: "teatro", confidence: "low", score: 40, event_id: "b", source_id: "portaltickets_valparaiso" },
    ],
  },
}, "teatro");

console.log("PUBLIC_CATEGORY_JS_REGRESSIONS_OK");
'''
    replace_once(path, marker2, insertion, "js dedup regressions")


def patch_python_regressions() -> None:
    path = ROOT / "app/scripts/test_public_category_regressions.py"
    marker = '''    audit_current_theatre_conflicts()
'''
    insertion = '''    merged_matriarcas = event(
        "Matriarcas: Poesía, Papel y Tinta",
        "teatro",
        description=(
            "Matriarcas es una obra sobre Gabriela Mistral, Alfonsina Storni y "
            "Juana de Ibarbourou, literatura latinoamericana, poesía, poetas y "
            "una histórica conferencia literaria."
        ),
        venue="Parque Cultural de Valparaíso",
        city="Valparaíso",
    )
    merged_matriarcas["semantics"] = {
        "source_category": {"id": "teatro", "label": "Teatro y danza"}
    }
    merged_matriarcas["editorial"] = {
        "merged_category_evidence": [
            {"category_id": "teatro", "confidence": "high", "score": 230, "event_id": "a", "source_id": "pcdv"},
            {"category_id": "teatro", "confidence": "low", "score": 40, "event_id": "b", "source_id": "portaltickets_valparaiso"},
        ]
    }
    assert_case(
        "merged category consensus beats prose-topic drift",
        merged_matriarcas,
        "teatro",
    )
    audit_current_theatre_conflicts()
'''
    replace_once(path, marker, insertion, "python merged consensus regression")


def main() -> None:
    patch_taxonomy()
    patch_identity_core()
    patch_js_classifier()
    patch_python_classifier()
    patch_js_regressions()
    patch_python_regressions()
    print("DEDUP_CATEGORY_CONSENSUS_PATCH_APPLIED")


if __name__ == "__main__":
    main()
