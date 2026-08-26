import assert from "node:assert/strict";
import test from "node:test";

import {
  applyDeclarativeEventCorrectionRules,
  isGenericPromotionalTitle,
} from "./event-correction-rules.mjs";

const dataset = {
  events: [{ id: "event-1", source_id: "source-a", categories: [{ id: "musica", label: "Música" }] }],
};
const rules = [{
  id: "official-category",
  cityId: "test-city",
  match: { sourceId: "source-a" },
  ensureCategories: [{ id: "teatro", label: "Teatro" }],
  authority: "official_program",
}];

test("applies declared corrections by city and records their authority", () => {
  const corrected = applyDeclarativeEventCorrectionRules(dataset, { cityId: "test-city", rules });
  assert.deepEqual(corrected.events[0].categories.map((category) => category.id), ["musica", "teatro"]);
  assert.deepEqual(corrected.events[0].editorial.applied_correction_rules, ["official-category"]);
  assert.equal(corrected.events[0].editorial.correction_authority, "official_program");
});

test("does not leak a city correction into another city and is idempotent", () => {
  assert.equal(applyDeclarativeEventCorrectionRules(dataset, { cityId: "other-city", rules }), dataset);
  const once = applyDeclarativeEventCorrectionRules(dataset, { cityId: "test-city", rules });
  assert.equal(applyDeclarativeEventCorrectionRules(once, { cityId: "test-city", rules }), once);
});

test("repairs the Sala Acapulco anime event from official-poster authority", () => {
  const input = {
    events: [{
      id: "gijon_sala_acapulco_conciertos_b7ba72ea73050459",
      title: "Entradas a la venta en sus redes",
      categories: [{ id: "musica", label: "Música" }],
      image: { url: "https://example.org/anime.jpg", alt: "Entradas a la venta en sus redes" },
    }],
  };

  const corrected = applyDeclarativeEventCorrectionRules(input, { cityId: "gijon" });
  assert.equal(corrected.events.length, 1);
  assert.equal(corrected.events[0].title, "La Mejor Fiesta Anime");
  assert.equal(corrected.events[0].image.alt, "La Mejor Fiesta Anime");
  assert.equal(corrected.events[0].editorial.title_original, "Entradas a la venta en sus redes");
  assert.equal(corrected.events[0].editorial.correction_authority, "official_poster");
  assert.deepEqual(corrected.events[0].editorial.applied_correction_rules, ["gijon-acapulco-anime-official-poster-title"]);
});

test("normalizes the Jazz Xixón recital title with editorial capitalization", () => {
  const input = {
    events: [{
      id: "jazz-xixon-recital",
      title: "Daniel garcía diego - pablo martín caminero. Recital 2.0 | jazz xixón",
      categories: [{ id: "musica", label: "Música" }],
    }],
  };

  const corrected = applyDeclarativeEventCorrectionRules(input, { cityId: "gijon" });
  assert.equal(corrected.events.length, 1);
  assert.equal(
    corrected.events[0].title,
    "Daniel García Diego - Pablo Martín Caminero. Recital 2.0 | Jazz Xixón",
  );
  assert.equal(corrected.events[0].editorial.correction_authority, "official_program_editorial_title");
});

test("rejects generic sales and information CTAs that are not event titles", () => {
  assert.equal(isGenericPromotionalTitle("Entradas a la venta en sus redes"), true);
  assert.equal(isGenericPromotionalTitle("Venta de entradas en taquilla"), true);
  assert.equal(isGenericPromotionalTitle("Consultar horario en la fuente"), true);
  assert.equal(isGenericPromotionalTitle("Más información"), true);

  const input = {
    events: [{
      id: "unknown-bad-title",
      title: "Entradas a la venta en sus redes",
      categories: [{ id: "musica", label: "Música" }],
    }],
  };
  const corrected = applyDeclarativeEventCorrectionRules(input, { cityId: "gijon" });
  assert.deepEqual(corrected.events, []);
});

test("does not reject a legitimate title that merely contains the word Entradas", () => {
  const input = {
    events: [{
      id: "legitimate-title",
      title: "Entradas para volver a verte",
      categories: [{ id: "teatro", label: "Teatro" }],
    }],
  };
  const corrected = applyDeclarativeEventCorrectionRules(input, { cityId: "gijon" });
  assert.equal(corrected, input);
});
