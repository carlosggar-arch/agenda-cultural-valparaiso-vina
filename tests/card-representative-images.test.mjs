import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../app/card-experience.js", import.meta.url), "utf8");
const css = await readFile(new URL("../app/card-experience.css", import.meta.url), "utf8");

test("representative images are restricted to the same normalized venue", () => {
  assert.match(source, /function venueImageKey\(event\)/);
  assert.match(source, /return key \? venueImagePools\.get\(key\)\?\.\[0\] \|\| null : null/);
  assert.match(source, /function buildVenueImagePools\(events\)/);
  assert.match(source, /const key = venueImageKey\(event\)/);
  assert.match(source, /return venue \? `\$\{city\}\|\$\{venue\}` : null/);
});

test("generic schedule art is never promoted to a representative event image", () => {
  assert.match(source, /function representativeImageUrl\(event\) \{\s*if \(looksLikeGenericSchedule\(event\)\) return null;/s);
  assert.match(source, /const url = relevantImageUrl\(event\)/);
});

test("representative imagery is clearly labelled and preserves placeholders", () => {
  assert.match(source, /image\.dataset\.eventImage = representative \? "representative" : "relevant"/);
  assert.match(source, /"event-card-image-note", "Imagen del recinto"/);
  assert.match(source, /addPlaceholder\(media, event, looksLikeGenericSchedule\(event\)\)/);
  assert.match(css, /\.event-card-image-note\{/);
});
