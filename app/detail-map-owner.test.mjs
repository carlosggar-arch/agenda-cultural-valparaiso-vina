import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";

const source = readFileSync(new URL("./schedule-display.js", import.meta.url), "utf8");
function body(name, next) {
  const start = source.indexOf(`function ${name}(`);
  const end = source.indexOf(`\nfunction ${next}(`, start);
  assert.ok(start >= 0 && end > start, `actual ${name} implementation must be present`);
  return source.slice(start, end);
}
const event = { destination: "https://www.google.com/maps/dir/?api=1&destination=Verified+Venue" };
const copy = {
  dataset: {}, nodes: [],
  querySelector(selector) { return selector === ".map-location-link" ? this.nodes.find(n => n.href) || null : null; },
  replaceChildren() { this.nodes = []; },
  append(...nodes) { this.nodes.push(...nodes); },
};
let primaryAction = { href: event.destination };
const fact = { querySelector: selector => selector === "strong" ? { textContent: "Lugar" } : copy };
const dialog = {
  querySelectorAll: () => [fact],
  querySelector: () => primaryAction,
};
const context = {
  document: { createTextNode: text => ({ textContent: text }) },
  googleMapsDirectionsUrl: current => current.destination || null,
  mapLinkForEvent: current => current.destination ? { href: current.destination, className: "map-location-link" } : null,
  locationForDisplay: () => "Verified Venue",
};
runInNewContext(body("replaceLocationCopy", "replaceLocationFactValue") + "\n" + body("replaceDetailLocation", "enhanceDetail"), context);
const links = () => copy.nodes.filter(n => n.href);
context.replaceDetailLocation(dialog, event);
assert.equal(links().length, 0, "a detail action already owns Maps; the schedule enhancer must not add a second link");
primaryAction = null;
context.replaceDetailLocation(dialog, event);
assert.equal(links().length, 1, "legacy details without a primary action retain inline Maps");
context.replaceDetailLocation(dialog, event);
assert.equal(links().length, 1, "repeated enhancement remains idempotent");
primaryAction = { href: event.destination };
context.replaceDetailLocation(dialog, event);
assert.equal(links().length, 0, "adding the primary action removes a previous inline duplicate");
context.replaceLocationCopy(copy, "Verified Venue", event, true);
assert.equal(links().length, 1, "ordinary cards retain inline navigation independently of any dialog");
primaryAction = null;
context.replaceDetailLocation(dialog, { destination: null });
assert.equal(links().length, 0, "missing destination cannot retain an old inline link");
console.log("DETAIL_MAP_OWNER_OK primary, fallback, idempotence, transitions, card, missing evidence");
