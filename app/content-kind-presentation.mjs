import { classifyContentKind } from "./temporal-priority-core.mjs?v=20260821-temporal4";

export const CONTENT_KIND_PRESENTATION = Object.freeze({
  dated_event: Object.freeze({
    label: "Fecha concreta",
    detail: "Actividad con una fecha u horario concreto.",
  }),
  long_running_event: Object.freeze({
    label: "En curso",
    detail: "Actividad disponible durante un periodo de varios días.",
  }),
  recurring_offer: Object.freeze({
    label: "Recurrente",
    detail: "Actividad que se repite de forma regular.",
  }),
  permanent_offer: Object.freeze({
    label: "Disponible",
    detail: "Actividad u oportunidad disponible de forma estable.",
  }),
  call_for_submissions: Object.freeze({
    label: "Convocatoria",
    detail: "Convocatoria cultural con plazo de participación; no es una función presencial.",
  }),
  undated: Object.freeze({
    label: "Fecha por confirmar",
    detail: "La fecha concreta todavía no está confirmada.",
  }),
});

/**
 * Shared visual semantics for content_kind. The classification remains owned by
 * temporal-priority-core; this module only translates that canonical meaning to
 * a compact public label and explanatory text used by every city.
 */
export function contentKindPresentation(event, city) {
  const kind = classifyContentKind(event, city);
  const presentation = CONTENT_KIND_PRESENTATION[kind] || CONTENT_KIND_PRESENTATION.undated;
  return Object.freeze({ kind, ...presentation });
}
