import assert from "node:assert/strict";
import test from "node:test";

import {
  isRootNonEventDescription,
  normalizeRootPublicEventTitle,
} from "../assets/root-public-presentation-rules.mjs";

const baseEvent = {
  location: { venue: "Teatro Municipal de Valparaíso", city: "Valparaíso" },
  primary_category: { id: "teatro", label: "Teatro" },
  categories: [{ id: "teatro", label: "Teatro" }],
};

test("WEB converts all-caps public titles while preserving acronyms", () => {
  assert.equal(
    normalizeRootPublicEventTitle("CONCIERTO HOMENAJE UTFSM", {
      ...baseEvent,
      primary_category: { id: "musica", label: "Música" },
      categories: [{ id: "musica", label: "Música" }],
    }),
    "Concierto Homenaje UTFSM",
  );
});

test("WEB removes generic format prefixes and outer quotes", () => {
  assert.equal(
    normalizeRootPublicEventTitle('TEATRO: “LA CASA DE BERNARDA ALBA”', baseEvent),
    "La Casa de Bernarda Alba",
  );
});

test("WEB removes redundant venue and city from the public title", () => {
  assert.equal(
    normalizeRootPublicEventTitle(
      "Hamlet en Teatro Municipal de Valparaíso, Valparaíso",
      baseEvent,
    ),
    "Hamlet",
  );
});

test("WEB uses sentence case for workshop/course all-caps titles", () => {
  const workshop = {
    ...baseEvent,
    primary_category: { id: "cursos-talleres", label: "Cursos y talleres" },
    categories: [{ id: "cursos-talleres", label: "Cursos y talleres" }],
  };
  assert.equal(
    normalizeRootPublicEventTitle("CICLO DE TALLERES: ARTE Y NATURALEZA", workshop),
    "Arte y naturaleza",
  );
});

test("WEB recognizes technical pipeline descriptions that should not be public", () => {
  assert.equal(
    isRootNonEventDescription("Evento detectado en Instagram utilizado como fuente secundaria"),
    true,
  );
  assert.equal(isRootNonEventDescription("Una obra sobre memoria y ciudad."), false);
});
