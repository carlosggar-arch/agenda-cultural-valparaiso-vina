from pathlib import Path

p = Path('app/event-identity-core.mjs')
text = p.read_text(encoding='utf-8')
old = '''function scheduleConflictDuplicate(a, b) {\n  if (!(hasAuthoritativeSource(a) || hasAuthoritativeSource(b))) return false;\n  if (!sameLocalOccurrenceDate(a, b)) return false;\n  if (minimumOccurrenceStartDifferenceMinutes(a, b) > SCHEDULE_CONFLICT_TOLERANCE_MINUTES) return false;\n  return recurringTitlesLikelySame(a?.title, b?.title);\n}\n'''
new = '''function scheduleDay(value) {\n  const match = String(value || "").match(/^(\\d{4}-\\d{2}-\\d{2})/u);\n  return match?.[1] || "";\n}\n\nfunction dayDistance(left, right) {\n  if (!(left && right)) return Number.POSITIVE_INFINITY;\n  const a = Date.parse(`${left}T00:00:00Z`);\n  const b = Date.parse(`${right}T00:00:00Z`);\n  if (!(Number.isFinite(a) && Number.isFinite(b))) return Number.POSITIVE_INFINITY;\n  return Math.abs(a - b) / 86400000;\n}\n\nfunction authoritativeMultiDayRangeDuplicate(a, b) {\n  if (!(hasAuthoritativeSource(a) || hasAuthoritativeSource(b))) return false;\n  if (!titlesLikelySame(a?.title, b?.title)) return false;\n  const startA = scheduleDay(a?.schedule?.start);\n  const startB = scheduleDay(b?.schedule?.start);\n  const endA = scheduleDay(a?.schedule?.end);\n  const endB = scheduleDay(b?.schedule?.end);\n  if (!(startA && startB && endA && endB)) return false;\n  // Long-running activities are sometimes published with the opening day in\n  // one source and the first public-visit day in another. Reconcile only when\n  // the closing boundary agrees exactly and the opening boundary differs by\n  // at most one calendar day; venue and title identity are checked by the\n  // caller before this rule can run.\n  if (endA !== endB) return false;\n  if (startA === endA || startB === endB) return false;\n  return dayDistance(startA, startB) <= 1;\n}\n\nfunction scheduleConflictDuplicate(a, b) {\n  if (!(hasAuthoritativeSource(a) || hasAuthoritativeSource(b))) return false;\n  if (!sameLocalOccurrenceDate(a, b)) return false;\n  if (minimumOccurrenceStartDifferenceMinutes(a, b) > SCHEDULE_CONFLICT_TOLERANCE_MINUTES) return false;\n  return recurringTitlesLikelySame(a?.title, b?.title);\n}\n'''
if text.count(old) != 1:
    raise SystemExit(f'range helper marker count={text.count(old)}')
text = text.replace(old, new, 1)
old = '''  if (sameLocalOccurrenceStart(a, b)) {\n    if (titlesLikelySame(a?.title, b?.title)) return true;\n'''
new = '''  if (sameLocalOccurrenceStart(a, b)) {\n    if (titlesLikelySame(a?.title, b?.title)) return true;\n'''
# keep anchor for deterministic second replacement
if text.count(old) != 1:
    raise SystemExit(f'probable anchor count={text.count(old)}')
old2 = '''  }\n  return scheduleConflictDuplicate(a, b);\n}\n\nexport function mergeDuplicateEvents'''
new2 = '''  }\n  if (authoritativeMultiDayRangeDuplicate(a, b)) return true;\n  return scheduleConflictDuplicate(a, b);\n}\n\nexport function mergeDuplicateEvents'''
if text.count(old2) != 1:
    raise SystemExit(f'probable range insertion count={text.count(old2)}')
text = text.replace(old2, new2, 1)
old3 = '''  if (scheduleConflictDuplicate(a, b)) return "same_date_similar_venue_recurring_title_authoritative_source";\n  return "cross_source_probable_duplicate";\n'''
new3 = '''  if (authoritativeMultiDayRangeDuplicate(a, b)) return "same_multiday_range_similar_venue_similar_title_authoritative_source";\n  if (scheduleConflictDuplicate(a, b)) return "same_date_similar_venue_recurring_title_authoritative_source";\n  return "cross_source_probable_duplicate";\n'''
if text.count(old3) != 1:
    raise SystemExit(f'dedup rule marker count={text.count(old3)}')
p.write_text(text.replace(old3, new3, 1), encoding='utf-8')

p = Path('app/cross-source-deduplication.test.mjs')
text = p.read_text(encoding='utf-8')
old = '''    start: "2026-08-03T00:00:00+02:00",\n    venue: "Primera planta del Antiguo Instituto Jovellanos",\n'''
new = '''    start: "2026-08-03T06:00:00+02:00",\n    venue: "Primera planta del Antiguo Instituto Jovellanos",\n'''
# only target the appended Gijon block; marker should be unique there.
if text.count(old) != 1:
    raise SystemExit(f'social test start count={text.count(old)}')
text = text.replace(old, new, 1)
old = '''  social.primary_category = { id: "teatro", label: "Teatro y danza" };\n'''
new = '''  social.schedule.end = "2026-08-30";\n  social.primary_category = { id: "teatro", label: "Teatro y danza" };\n'''
if text.count(old) != 1:
    raise SystemExit(f'social end marker count={text.count(old)}')
text = text.replace(old, new, 1)
old = '''    start: "2026-08-03T00:00:00+02:00",\n    venue: "Centro de Cultura Antiguo Instituto",\n'''
new = '''    start: "2026-08-04",\n    venue: "Centro de Cultura Antiguo Instituto",\n'''
if text.count(old) != 1:
    raise SystemExit(f'official test start count={text.count(old)}')
text = text.replace(old, new, 1)
old = '''  official.primary_category = { id: "exposiciones", label: "Exposiciones" };\n'''
new = '''  official.schedule.end = "2026-08-30";\n  official.primary_category = { id: "exposiciones", label: "Exposiciones" };\n'''
if text.count(old) != 1:
    raise SystemExit(f'official end marker count={text.count(old)}')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')
print('GIJON_MULTIDAY_RANGE_IDENTITY_PATCH_APPLIED')
