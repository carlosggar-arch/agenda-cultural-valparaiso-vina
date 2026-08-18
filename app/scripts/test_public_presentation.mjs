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
    start: "2026-08-18",
    end: "2026-08-30",
    display_text: "18 al 30 de agosto · Martes a domingo · 10:00–17:30",
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

console.log("PUBLIC_PRESENTATION_RULES_TESTS_OK");
