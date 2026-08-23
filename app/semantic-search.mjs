function clean(value) {
  return String(value || "").trim();
}

export function semanticSearchTerms(event = {}) {
  const semantics = event?.semantics || {};
  const trace = semantics?.trace || {};
  const promotedDomains = new Set([
    semantics?.primary_domain,
    ...(semantics?.secondary_domains || []),
  ].filter(Boolean));
  const promotedDomainLabels = (semantics?.domain_candidates || [])
    .filter((candidate) => promotedDomains.has(candidate?.category?.id))
    .map((candidate) => candidate?.category?.label)
    .filter(Boolean);
  const values = [
    ...promotedDomains,
    ...promotedDomainLabels,
    semantics?.format,
    trace?.format?.label,
    semantics?.audience,
    trace?.audience?.label,
    semantics?.lifecycle,
  ].map(clean).filter(Boolean);
  return [...new Set(values)];
}
