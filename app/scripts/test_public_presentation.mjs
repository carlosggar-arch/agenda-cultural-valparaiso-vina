import assert from "node:assert/strict";
import {
  groupedScheduleLabel,
  isNonEventDescription,
  normalizePublicTitle,
  publicLocationLabel,
} from "../public-presentation-rules.mjs";

const casa = {
  title: "Casa de la Cultura de Valparaíso – Luciana Jury en Chile",
  location: { venue: "Casa de la Cultura de Valparaíso", city: "Valparaíso" },
};
assert.equal(normalizePublicTitle(casa.title, casa), "Luciana Jury en Chile");

const parque = {
  title: "Música ensamble presenta “notas que transforman” en parque cultural de valparaíso",
  location: { venue: "Parque Cultural de Valparaíso – Ex Cárcel, Valparaíso", city: "Valparaíso" },
};
assert.equal(
  normalizePublicTitle(parque.title, parque),
  "Música ensamble presenta “notas que transforman”",
);

const artequin = {
  title: "Ciclo taller EL ARTE ES NATURAL",
  primary_category: { id: "cursos-talleres", label: "Cursos y talleres" },
  location: { venue: "Museo Artequin Viña del Mar", city: "Viña del Mar" },
};
assert.equal(normalizePublicTitle(artequin.title, artequin), "EL ARTE ES NATURAL");

const tanquemante = {
  title: "INUNDAREMOS EN VALPARAÍSO - GIRA TANQUEMANTE",
  primary_category: { id: "musica", label: "Música" },
  location: { venue: "Espacio la Compañía, Valparaíso", city: "Valparaíso" },
};
assert.equal(normalizePublicTitle(tanquemante.title, tanquemante), "Inundaremos — Gira Tanquemante");

assert.equal(
  isNonEventDescription("Cobertura municipal oficial de programación de Casa de la Cultura de Valparaíso."),
  true,
);
assert.equal(
  isNonEventDescription("Evento detectado en PortalTickets, utilizado como ticketera y fuente secundaria estructurada."),
  true,
);
assert.equal(
  isNonEventDescription("Luciana Jury presenta un concierto íntimo con repertorio latinoamericano."),
  false,
);

const museo = {
  location: { venue: "Museo Palacio Rioja", city: "Viña del Mar" },
  schedule: {
    start: "2026-08-18T16:00:00-04:00",
    end: "2026-08-30",
    display_text: "18 al 30 de agosto",
    opening_hours: {
      opening_time: "10:00",
      closing_time: "17:30",
      display_text: "Martes a domingo · 10:00–17:30",
    },
  },
};
assert.equal(publicLocationLabel(museo), "Museo Palacio Rioja · Viña del Mar");
const grouped = groupedScheduleLabel(museo, {
  locale: "es-CL",
  timezone: "America/Santiago",
  now: new Date("2026-08-18T12:00:00-04:00"),
});
assert.match(grouped, /^En exhibición hasta el /);
assert.match(grouped, /10:00–17:30$/);
assert.doesNotMatch(grouped, /16:00/);

console.log("PUBLIC_PRESENTATION_RULES_TESTS_OK");
