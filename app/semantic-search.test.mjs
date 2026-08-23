import assert from "node:assert/strict";
import fs from "node:fs";
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

const combinedFiltersSource = fs.readFileSync(new URL("./combined-filters.js", import.meta.url), "utf8");
assert.match(
  combinedFiltersSource,
  /import\s*\{\s*semanticSearchTerms\s*\}\s*from\s*["']\.\/semantic-search\.mjs["']/,
  "canonical smart search must import semanticSearchTerms",
);
assert.match(
  combinedFiltersSource,
  /function\s+eventSearchText\([^)]*\)[\s\S]*\.\.\.semanticSearchTerms\(event\)/,
  "canonical smart search haystack must include semanticSearchTerms(event)",
);
const categoryMatcher = combinedFiltersSource.match(/function\s+eventMatchesCategories\([^)]*\)\s*\{([\s\S]*?)\n\}/)?.[1] || "";
assert.equal(categoryMatcher.includes("semanticSearchTerms"), false, "semantic dimensions must not become thematic category filters");

console.log("SEMANTIC_SEARCH_ISOLATION_OK");
