import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const cards = await readFile(new URL("../app/card-experience.js", import.meta.url), "utf8");
const resolver = await readFile(new URL("../app/image-resolver-core.mjs", import.meta.url), "utf8");
const css = await readFile(new URL("../app/card-experience.css", import.meta.url), "utf8");

test("representative images are restricted to the same normalized venue", () => {
  assert.match(cards, /buildVenueImagePools/);
  assert.match(cards, /resolveEventImage/);
  assert.match(resolver, /export function venueImageKey\(event\)/);
  assert.match(resolver, /return key \? venueImagePools\?\.get\(key\)\?\.\[0\] \|\| null : null/);
  assert.match(resolver, /export function buildVenueImagePools\(events/);
  assert.match(resolver, /const key = venueImageKey\(event\)/);
  assert.match(resolver, /return venue \? `\$\{city\}\|\$\{venue\}` : null/);
});

test("generic schedule art is never promoted to a representative event image", () => {
  assert.match(resolver, /export function representativeVenueImageUrl\(event, venueImagePools\) \{\s*if \(looksLikeGenericSchedule\(event\)\) return null;/s);
  assert.match(resolver, /const url = relevantEventImageUrl\(event, \{ baseUrl \}\)/);
});

test("representative imagery is clearly labelled and preserves placeholders", () => {
  assert.match(cards, /image\.dataset\.eventImage = representative \? "representative" : "relevant"/);
  assert.match(cards, /"event-card-image-note", "Imagen del recinto"/);
  assert.match(cards, /addPlaceholder\(media, event, resolved\.genericSchedule\)/);
  assert.match(css, /\.event-card-image-note\{/);
});

test("all card image decisions are delegated to the canonical resolver", () => {
  assert.match(cards, /from "\.\/image-resolver-core\.mjs\?v=/);
  assert.doesNotMatch(cards, /function venueImageKey\(/);
  assert.doesNotMatch(cards, /function buildVenueImagePools\(/);
  assert.doesNotMatch(cards, /function looksLikeGenericSchedule\(/);
  assert.doesNotMatch(cards, /function representativeImageUrl\(/);
});
