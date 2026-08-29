import assert from "node:assert/strict";
import test from "node:test";

import { countDisplayCards, displayCardLookup } from "./visible-display-card-core.mjs";

const card = (dataset) => ({ dataset });
const event = (id) => ({ id });

test("grouped source records count as one visible display card", () => {
  const lookup = displayCardLookup([
    card({ eventGroup: "expo-b,expo-a" }),
    card({ eventId: "concert" }),
  ]);
  assert.equal(countDisplayCards([event("expo-a"), event("expo-b"), event("concert")], lookup), 2);
});

test("a facet replacement counts only matching visible cards", () => {
  const lookup = displayCardLookup([
    card({ eventGroup: "expo-a,expo-b" }),
    card({ eventId: "music" }),
  ]);
  assert.equal(countDisplayCards([event("expo-b")], lookup), 1);
  assert.equal(countDisplayCards([event("music")], lookup), 1);
});

test("dataset rows without a renderable card never inflate a facet", () => {
  assert.equal(countDisplayCards([event("charla-hidden")], new Map()), 0);
});
