import { compareTemporalPriority } from "./temporal-priority-core.mjs?v=20260821-temporal4";

function fold(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .trim();
}

function finiteWeight(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function categoryId(event) {
  return String(event?.primary_category?.id || event?.categories?.[0]?.id || "").trim();
}

function eventAreaId(event, city, areaWeights) {
  const place = fold([event?.location?.city, event?.location?.commune].filter(Boolean).join(" "));
  if (!place) return null;

  const rankedAreas = (city?.areas || [])
    .map((area, index) => ({
      area,
      index,
      weight: finiteWeight(areaWeights?.[area?.id], Number.POSITIVE_INFINITY),
    }))
    .filter(({ area }) => area?.id && area.id !== "todos")
    .sort((left, right) => left.weight - right.weight || left.index - right.index);

  for (const { area } of rankedAreas) {
    const matches = Array.isArray(area?.match) ? area.match : [];
    if (matches.some((candidate) => {
      const token = fold(candidate);
      return token && place.includes(token);
    })) return area.id;
  }
  return null;
}

/**
 * Compatibility-preserving presentation rank for top-level agenda cards.
 *
 * The policy is data-driven per city. Cities without a presentation_order
 * configuration get rank 0, so their visible order is purely temporal.
 */
export function agendaPresentationRank(event, city) {
  const policy = city?.presentation_order;
  if (!policy || typeof policy !== "object") return 0;

  const categoryWeights = policy.category_weights || {};
  const areaWeights = policy.area_weights || {};
  const categoryRank = finiteWeight(categoryWeights[categoryId(event)], 0);
  const defaultAreaRank = finiteWeight(policy.default_area_weight, 0);
  const areaId = eventAreaId(event, city, areaWeights);
  const areaRank = areaId
    ? finiteWeight(areaWeights[areaId], defaultAreaRank)
    : defaultAreaRank;
  return categoryRank + areaRank;
}

/**
 * Single authority for visible agenda ordering.
 *
 * Presentation grouping is compared first only to preserve the public order
 * that historically came from CSS `order`. Within the same presentation rank,
 * temporal-priority-core remains the sole semantic authority.
 */
export function compareAgendaOrder(a, b, city, now = new Date()) {
  const presentationDiff = agendaPresentationRank(a, city) - agendaPresentationRank(b, city);
  if (presentationDiff) return presentationDiff;
  return compareTemporalPriority(a, b, city, now);
}
