import { applyCanonicalSourceEvidence } from "./source-evidence-policy.mjs";

export function normalizeAgendaSourceEvidence(dataset) {
  if (!dataset || !Array.isArray(dataset.events)) return dataset;

  let changed = false;
  const events = dataset.events.map((event) => {
    const normalized = applyCanonicalSourceEvidence(event);
    const samePrimary = normalized.source_url === event?.source_url;
    const sameSecondaries = JSON.stringify(normalized.secondary_source_urls || [])
      === JSON.stringify(event?.secondary_source_urls || []);
    const sameSourceLink = normalized?.links?.source === event?.links?.source;
    const sameIdentity = normalized.source_id === event?.source_id && normalized.source_name === event?.source_name;
    if (samePrimary && sameSecondaries && sameSourceLink && sameIdentity) return event;
    changed = true;
    return normalized;
  });

  return changed ? { ...dataset, events } : dataset;
}
