import { normalizePublicEventTitle } from "./public-title-normalizer.mjs?v=20260818-title3";

function factValue(card, label) {
  for (const row of card.querySelectorAll(".card-fact")) {
    const sr = row.querySelector(".sr-only");
    if (!sr || !sr.textContent.trim().toLocaleLowerCase("es").startsWith(`${label.toLocaleLowerCase("es")}:`)) continue;
    const icon = row.querySelector(".card-fact-icon")?.textContent || "";
    const value = row.textContent.replace(sr.textContent, "").replace(icon, "").trim();
    if (value) return value;
  }
  return "";
}

function eventContextForCard(card) {
  const categoryLabel = card.querySelector(".meta")?.textContent?.trim() || "";
  const categoryId = String(card.dataset.category || "").trim();
  const location = factValue(card, "Lugar");
  const parts = location.split("·").map((part) => part.trim()).filter(Boolean);
  const city = parts.length > 1 ? parts.at(-1) : "";
  const venue = parts.length > 1 ? parts.slice(0, -1).join(" · ") : parts[0] || "";
  return {
    primary_category: { id: categoryId, label: categoryLabel },
    categories: categoryLabel ? [{ id: categoryId, label: categoryLabel }] : [],
    location: { venue, city },
  };
}

function normalizeCardTitle(card) {
  if (!(card instanceof Element)) return;
  const heading = card.querySelector("h4");
  if (!heading) return;
  const current = String(heading.textContent || "").replace(/\s+/g, " ").trim();
  if (!current) return;
  const normalized = normalizePublicEventTitle(current, eventContextForCard(card));
  if (normalized && normalized !== current) heading.textContent = normalized;
}

function normalizeTree(node) {
  if (!(node instanceof Element)) return;
  if (node.matches(".event-card[data-event-id]")) normalizeCardTitle(node);
  node.querySelectorAll?.(".event-card[data-event-id]").forEach(normalizeCardTitle);
}

const roots = [
  document.querySelector("[data-dated-grid]"),
  document.querySelector("[data-program-grid]"),
  document.querySelector("[data-flexible-grid]"),
].filter(Boolean);

for (const root of roots) normalizeTree(root);

const observer = new MutationObserver((records) => {
  for (const record of records) {
    const targetCard = record.target instanceof Element
      ? record.target.closest(".event-card[data-event-id]")
      : record.target.parentElement?.closest(".event-card[data-event-id]");
    if (targetCard) normalizeCardTitle(targetCard);
    for (const node of record.addedNodes) normalizeTree(node);
  }
});

for (const root of roots) {
  observer.observe(root, { childList: true, subtree: true, characterData: true });
}
