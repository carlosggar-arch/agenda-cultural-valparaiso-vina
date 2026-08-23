import assert from "node:assert/strict";
import { semanticSearchTerms } from "./semantic-search.mjs";

const event = {
  title: "Taller de teatro físico",
  semantics: {
    primary_domain: "cursos-talleres-campus",
    secondary_domains: ["teatro"],
    format: "taller",
    audience: "familiar",
    lifecycle: "dated_event",
    domain_candidates: [
      { category: { id: "cursos-talleres-campus", label: "Cursos, talleres y experiencias" } },
      { category: { id: "teatro", label: "Teatro y artes escénicas" } },
      { category: { id: "cine", label: "Cine" } },
    ],
    trace: {
      format: { label: "Taller" },
      audience: { label: "Familiar" },
    },
  },
};

const terms = semanticSearchTerms(event);
for (const expected of [
  "cursos-talleres-campus",
  "teatro",
  "Teatro y artes escénicas",
  "taller",
  "Taller",
  "familiar",
  "Familiar",
  "dated_event",
]) assert.ok(terms.includes(expected), `missing semantic search term ${expected}`);

assert.equal(terms.includes("Cine"), false, "weak non-promoted domain candidate must not leak into search");
assert.equal(event.semantics.primary_domain, "cursos-talleres-campus");
assert.deepEqual(event.semantics.secondary_domains, ["teatro"]);
assert.equal(event.title, "Taller de teatro físico");

console.log("SEMANTIC_SEARCH_ISOLATION_OK");
