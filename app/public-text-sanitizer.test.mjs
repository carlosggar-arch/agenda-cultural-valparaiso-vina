import assert from "node:assert/strict";
import {
  decodePublicHtmlEntities,
  normalizeAgendaPublicText,
  normalizePublicDescriptionCase,
  plainPublicText,
} from "./public-text-sanitizer.mjs";

assert.equal(plainPublicText("Hola <p>mundo</p>"), "Hola mundo");
assert.equal(plainPublicText("Hola &lt;p&gt;mundo&lt;/p&gt;"), "Hola mundo");
assert.equal(plainPublicText("Hola &amp;lt;p&amp;gt;mundo&amp;lt;/p&amp;gt;"), "Hola mundo");
assert.equal(plainPublicText("Uno<br>Dos<br />Tres"), "Uno Dos Tres");
assert.equal(plainPublicText("<script>alert('x')</script>Evento"), "Evento");
assert.equal(plainPublicText("<style>p{display:none}</style>Evento"), "Evento");
assert.equal(plainPublicText("2 < 3 y 5 > 4"), "2 < 3 y 5 > 4", "ordinary comparison signs are not HTML tags");
assert.equal(decodePublicHtmlEntities("Rock &amp; roll"), "Rock & roll");

const jazzPromo = "🎷✨ TERRAZAS A LA CALLE | GRAN CIERRE DEL XI FESTIVAL INTERNACIONAL DE JAZZ DE VALPARAÍSO · Ven a disfrutar.";
assert.equal(
  normalizePublicDescriptionCase(jazzPromo),
  "🎷✨ Terrazas a la calle | Gran cierre del XI festival internacional de jazz de valparaíso · Ven a disfrutar.",
);

const caletaPromo = "📚✨ CLUB DE LECTURA PARA LA NIÑEZ | “CALETA DE HISTORIAS” ¡Las historias están esperando por ti!";
const caletaNormalized = normalizePublicDescriptionCase(caletaPromo);
assert.equal(
  caletaNormalized,
  "📚✨ Club de lectura para la niñez | “Caleta de historias” ¡Las historias están esperando por ti!",
);
assert.equal(normalizePublicDescriptionCase(caletaNormalized), caletaNormalized, "description case normalization must be idempotent");
assert.equal(
  normalizePublicDescriptionCase("Taller de fotografía con DJ invitado y público general."),
  "Taller de fotografía con DJ invitado y público general.",
  "mixed-case prose must remain untouched",
);
assert.equal(normalizePublicDescriptionCase("DJ SET esta noche"), "DJ set esta noche", "known acronyms remain uppercase");

const original = {
  events: [{
    id: "html-leak",
    title: "<p>Concierto de prueba</p>",
    description: "<div>Una <strong>actividad</strong> cultural</div>",
    organizer: "<span>Organizador</span>",
    source_name: "Fuente &amp; Cultura",
    primary_category: { id: "musica", label: "<b>Música</b>" },
    categories: [{ id: "musica", label: "&lt;p&gt;Música&lt;/p&gt;" }],
    schedule: {
      start: "2026-08-22T19:00:00-04:00",
      display_text: "<p>22 ago · 19:00</p>",
      opening_hours: { display_text: "<p>10:00–18:00</p>", source_url: "https://example.test/hours?a=<p>" },
      occurrences: [{ start: "2026-08-22T19:00:00-04:00", display_text: "<span>19:00</span>" }],
    },
    location: { venue: "<p>Teatro</p>", city: "Valparaíso", address: "<span>Calle 1</span>" },
    price: { display_text: "<b>$5.000</b>" },
    public_status: { advisory_text: "<p>Confirmar antes de asistir</p>" },
    image: { alt: "<p>Cartel</p>", url: "https://example.test/image?p=<p>" },
    tags: ["<i>música</i>", "noche"],
    links: { official: "https://example.test/event?p=<p>" },
    source_url: "https://example.test/source?p=<p>",
  }, {
    id: "caleta-description",
    title: "Caleta de Historias",
    description: caletaPromo,
    links: {},
  }],
};

const normalized = normalizeAgendaPublicText(original);
const event = normalized.events[0];
assert.equal(event.title, "Concierto de prueba");
assert.equal(event.description, "Una actividad cultural");
assert.equal(event.organizer, "Organizador");
assert.equal(event.source_name, "Fuente & Cultura");
assert.equal(event.primary_category.label, "Música");
assert.equal(event.categories[0].label, "Música");
assert.equal(event.schedule.display_text, "22 ago · 19:00");
assert.equal(event.schedule.opening_hours.display_text, "10:00–18:00");
assert.equal(event.schedule.occurrences[0].display_text, "19:00");
assert.equal(event.location.venue, "Teatro");
assert.equal(event.location.address, "Calle 1");
assert.equal(event.price.display_text, "$5.000");
assert.equal(event.public_status.advisory_text, "Confirmar antes de asistir");
assert.equal(event.image.alt, "Cartel");
assert.deepEqual(event.tags, ["música", "noche"]);
assert.equal(normalized.events[1].description, caletaNormalized);

// Structural invariant: transport fields are never rewritten as display text.
assert.equal(event.links.official, original.events[0].links.official);
assert.equal(event.source_url, original.events[0].source_url);
assert.equal(event.image.url, original.events[0].image.url);
assert.equal(event.schedule.opening_hours.source_url, original.events[0].schedule.opening_hours.source_url);

console.log("PUBLIC_TEXT_SANITIZER_OK");
