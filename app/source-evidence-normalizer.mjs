import { applyCanonicalSourceEvidence, normalizeSourceUrl } from "./source-evidence-policy.mjs";

function preferredStructuredEvidence(event) {
  const entries = Array.isArray(event?.source_evidence) ? event.source_evidence : [];
  for (const item of entries) {
    if (item?.presentation_preferred !== true) continue;
    const rawUrl = String(item?.url || "").trim();
    const canonicalUrl = normalizeSourceUrl(rawUrl);
    if (!canonicalUrl) continue;
    return { ...item, url: rawUrl, canonical_url: canonicalUrl };
  }
  return null;
}

function uniqueUrls(values) {
  const seen = new Set();
  const output = [];
  for (const value of values || []) {
    const url = normalizeSourceUrl(value);
    if (!url || seen.has(url)) continue;
    seen.add(url);
    output.push(url);
  }
  return output;
}

function applyPreferredStructuredEvidence(event, canonical) {
  const preferred = preferredStructuredEvidence(event);
  if (!preferred) return canonical;

  const secondary = uniqueUrls([
    canonical?.source_url,
    ...(canonical?.secondary_source_urls || []),
  ]).filter((url) => url !== preferred.canonical_url);
  const links = {
    ...(canonical?.links || {}),
    source: preferred.url,
    official: preferred.url,
    presentation_source: preferred.url,
  };

  return {
    ...canonical,
    source_name: String(preferred.source_name || canonical?.source_name || canonical?.organizer || "").trim() || null,
    source_url: preferred.url,
    secondary_source_urls: secondary,
    links,
  };
}

export function normalizeAgendaSourceEvidence(dataset) {
  if (!dataset || !Array.isArray(dataset.events)) return dataset;

  let changed = false;
  const events = dataset.events.map((event) => {
    const canonical = applyCanonicalSourceEvidence(event);
    const normalized = applyPreferredStructuredEvidence(event, canonical);
    const samePrimary = normalized.source_url === event?.source_url;
    const sameSecondaries = JSON.stringify(normalized.secondary_source_urls || [])
      === JSON.stringify(event?.secondary_source_urls || []);
    const sameSourceLink = normalized?.links?.source === event?.links?.source;
    const sameOfficialLink = normalized?.links?.official === event?.links?.official;
    const samePresentationLink = normalized?.links?.presentation_source === event?.links?.presentation_source;
    const sameIdentity = normalized.source_id === event?.source_id && normalized.source_name === event?.source_name;
    if (samePrimary && sameSecondaries && sameSourceLink && sameOfficialLink && samePresentationLink && sameIdentity) return event;
    changed = true;
    return normalized;
  });

  return changed ? { ...dataset, events } : dataset;
}
