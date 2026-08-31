function normalizedId(value) {
  return String(value ?? "").trim();
}

export function displayCardLookup(cards) {
  const lookup = new Map();
  for (const card of cards || []) {
    const directId = normalizedId(card?.dataset?.eventId);
    if (directId) {
      lookup.set(directId, `event:${directId}`);
      continue;
    }
    const memberIds = normalizedId(card?.dataset?.eventGroup)
      .split(",")
      .map(normalizedId)
      .filter(Boolean);
    if (!memberIds.length) continue;
    const cardId = `group:${[...memberIds].sort().join(",")}`;
    for (const memberId of memberIds) lookup.set(memberId, cardId);
  }
  return lookup;
}

export function countDisplayCards(events, lookup) {
  const cardIds = new Set();
  for (const event of events || []) {
    const eventId = normalizedId(event?.id);
    if (!eventId) continue;
    const cardId = lookup?.get(eventId);
    if (cardId) cardIds.add(cardId);
  }
  return cardIds.size;
}
