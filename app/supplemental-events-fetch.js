function canonicalLink(event) {
  const value = event?.links?.official || event?.links?.source || event?.source_url;
  if (!value) return "";
  try {
    const url = new URL(String(value), "https://example.invalid/");
    url.hash = "";
    return url.href.replace(/\/$/, "");
  } catch {
    return String(value).trim().replace(/\/$/, "");
  }
}

export function mergeEvents(baseEvents, supplementalEvents) {
  const merged = [...(Array.isArray(baseEvents) ? baseEvents : [])];
  const ids = new Set(merged.map((event) => String(event?.id || "").trim()).filter(Boolean));
  const links = new Set(merged.map(canonicalLink).filter(Boolean));

  for (const event of Array.isArray(supplementalEvents) ? supplementalEvents : []) {
    const id = String(event?.id || "").trim();
    const link = canonicalLink(event);
    if ((id && ids.has(id)) || (link && links.has(link))) continue;
    merged.push(event);
    if (id) ids.add(id);
    if (link) links.add(link);
  }
  return merged;
}

function withMergedCounts(payload, events, baseLength) {
  const added = Math.max(0, events.length - baseLength);
  if (!added || !payload?.counts || typeof payload.counts !== "object") return payload?.counts;
  const counts = { ...payload.counts };
  if (Number.isFinite(Number(counts.total))) counts.total = Number(counts.total) + added;
  if (Number.isFinite(Number(counts.events))) counts.events = Number(counts.events) + added;
  return counts;
}

export function mergeSupplementalPayload(basePayload, supplementalPayload) {
  if (!basePayload || !Array.isArray(basePayload.events)) return basePayload;
  if (!supplementalPayload || !Array.isArray(supplementalPayload.events)) return basePayload;
  const events = mergeEvents(basePayload.events, supplementalPayload.events);
  if (events.length === basePayload.events.length) return basePayload;
  return {
    ...basePayload,
    events,
    counts: withMergedCounts(basePayload, events, basePayload.events.length),
  };
}
