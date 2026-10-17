import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { constants, runInNewContext } from "node:vm";

import { isGenericProviderImage } from "../app/image-resolver-core.mjs";

const FLAG = "https://visitavina.munivina.cl/wp-content/uploads/2023/02/bandera-chile.svg";
const POSTER = "https://example.test/events/exposicion-banderas-2026.jpg";
const pageSource = readFileSync(new URL("./event-page.js", import.meta.url), "utf8");
const heroSource = pageSource.slice(pageSource.indexOf("  const heroImage ="), pageSource.indexOf("  function safeHttpUrl("));
assert.ok(heroSource.includes("removeBrokenHero"), "exercise the permanent page's actual hero behavior");

async function renderHero(url, { complete = true, naturalWidth = 640, city = "valparaiso" } = {}) {
  const classes = new Set();
  const listeners = new Map();
  const media = { removed: false, remove() { this.removed = true; } };
  const sheet = { classList: { add: (value) => classes.add(value) } };
  const image = {
    src: url, currentSrc: url, complete, naturalWidth,
    closest: (selector) => selector === ".event-hero-media" ? media : sheet,
    addEventListener: (type, listener) => listeners.set(type, listener),
  };
  await runInNewContext(heroSource, {
    scriptUrl: new URL("./event-page.js", import.meta.url).href,
    document: { body: { dataset: { city } }, querySelector: () => image },
    URL,
    console,
  }, { importModuleDynamically: constants.USE_MAIN_CONTEXT_DEFAULT_LOADER });
  return { media, classes, image, listeners };
}

for (const city of ["valparaiso", "gijon"]) {
  test(`permanent ${city} page removes a successfully loaded site flag`, async () => {
    const rendered = await renderHero(FLAG, { city });
    assert.equal(rendered.image.naturalWidth, 640, "the flag is valid artwork technically, not a failed download");
    assert.equal(rendered.media.removed, true);
    assert.ok(rendered.classes.has("event-sheet--no-media"));
  });

  test(`permanent ${city} page keeps a valid event poster`, async () => {
    const rendered = await renderHero(POSTER, { city });
    assert.equal(rendered.media.removed, false);
    assert.equal(rendered.classes.has("event-sheet--no-media"), false);
    assert.equal(rendered.image.src, POSTER);
  });
}

test("permanent page keeps the existing immediate and later image-error fallback", async () => {
  const failed = await renderHero(POSTER, { naturalWidth: 0 });
  assert.equal(failed.media.removed, true);
  assert.ok(failed.classes.has("event-sheet--no-media"));
  const pending = await renderHero(POSTER, { complete: false, naturalWidth: 0 });
  assert.equal(pending.media.removed, false);
  pending.listeners.get("error")();
  assert.equal(pending.media.removed, true);
  assert.ok(pending.classes.has("event-sheet--no-media"));
});

const enhancementSource = readFileSync(new URL("./web-event-enhancements.js", import.meta.url), "utf8");
function implementation(first, next) {
  const start = enhancementSource.indexOf(`function ${first}(`);
  const end = enhancementSource.indexOf(`\n${next}`, start);
  assert.ok(start >= 0 && end > start, `actual ${first} implementation must be present`);
  return enhancementSource.slice(start, end);
}

function renderRootDetail(event) {
  const styles = new Map();
  const classes = new Set();
  const image = { src: "https://example.test/category-exposiciones.jpg", dataset: {} };
  const media = {
    dataset: {},
    classList: { add: (value) => classes.add(value), remove: (value) => classes.delete(value) },
    style: { setProperty: (key, value) => styles.set(key, value), removeProperty: (key) => styles.delete(key) },
    querySelector: (selector) => selector === "img" ? image : null,
    querySelectorAll: () => [],
  };
  const dialog = {
    open: true,
    querySelector: (selector) => selector === ".card-media" ? media : null,
    querySelectorAll: () => [],
  };
  const context = {
    URL,
    window: { location: { href: "https://example.test/agenda/" } },
    document: { querySelector: () => dialog },
    isGenericProviderImage,
    MONTH_PATTERN: "enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre",
    normalizedPublicTitle: (value) => value.title,
    setTextIfChanged: () => {},
    installLocationNavigation: () => {},
    eventPageHref: () => null,
  };
  runInNewContext([
    implementation("validHttpUrl", "function sourceUrl("),
    implementation("looksLikeGenericSchedule", "function fallbackArtwork("),
    implementation("removeMediaOverlays", "function installImageTreatment("),
    implementation("enhanceDetail", "async function start("),
  ].join("\n"), context);
  context.enhanceDetail(event);
  return { styles, classes, image, relevantImageUrl: context.relevantImageUrl };
}

test("root detail enhancement does not restore a site flag over the category fallback", () => {
  const event = { title: "La Playa", image: { url: FLAG, relevance: "event_specific" } };
  const original = structuredClone(event);
  const rendered = renderRootDetail(event);
  assert.equal(rendered.styles.has("--event-image"), false);
  assert.equal(rendered.classes.has("has-relevant-image"), false);
  assert.equal(rendered.image.dataset.eventImage, undefined);
  assert.equal(rendered.image.src, "https://example.test/category-exposiciones.jpg");
  assert.deepEqual(event, original);
});

test("root detail enhancement keeps posters and the existing generic-schedule rejection", () => {
  const rendered = renderRootDetail({ title: "La Playa", image: { url: POSTER } });
  assert.equal(rendered.styles.get("--event-image"), `url("${POSTER}")`);
  assert.ok(rendered.classes.has("has-relevant-image"));
  assert.equal(rendered.image.dataset.eventImage, "relevant");
  assert.equal(rendered.relevantImageUrl({ title: "La Playa", image: { url: POSTER, relevance: "generic_schedule" } }), null);
  assert.equal(rendered.relevantImageUrl({ title: "Programación de octubre", image: { url: POSTER } }), null);
});
