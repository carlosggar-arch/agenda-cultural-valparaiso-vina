function categoryId(event) {
  return event.primary_category?.id || event.categories?.[0]?.id || "cultura";
}

function score(event, alertIds) {
  return Number(alertIds.has(event.id)) * 16
    + Number(event.public_status?.source_official === true) * 12
    + Number(event.public_status?.information_completeness === "complete") * 8
    + Number(Boolean(event.links?.registration)) * 4
    + Number(event.price?.is_free === true);
}

export function selectFeatured(events, alerts = [], limit = 3) {
  const alertIds = new Set(alerts.map((alert) => alert.event_id));
  const ranked = events
    .filter((event) => event.public_status?.cancelled !== true)
    .map((event, order) => ({ event, order, score: score(event, alertIds) }))
    .sort((a, b) => b.score - a.score || a.order - b.order);
  const chosen = [];
  const categories = new Set();
  for (const item of ranked) {
    const category = categoryId(item.event);
    if (!categories.has(category)) {
      chosen.push(item.event);
      categories.add(category);
    }
    if (chosen.length === limit) return chosen;
  }
  for (const item of ranked) {
    if (chosen.length === limit) break;
    if (!chosen.includes(item.event)) chosen.push(item.event);
  }
  return chosen;
}
