import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { filterSources, sourceDisplayName } from "../assets/fuentes.js";

const dataset = JSON.parse(await readFile(new URL("../fuentes_publicas.json", import.meta.url), "utf8"));
const PUBLIC_ID = "fuente_5c58c0825171c93a";


test("Insomnia keeps one public source ID and official URL", () => {
  const matches = dataset.sources.filter((source) => source.id === PUBLIC_ID || /insomnia|teatro condell/i.test(source.name));
  assert.equal(matches.length, 1);
  assert.equal(matches[0].id, PUBLIC_ID);
  assert.equal(matches[0].website_url, "https://www.insomniacine.cl");
  assert.equal(sourceDisplayName(matches[0]), "INSOMNIA Teatro Condell");
});


test("canonical and legacy names both remain searchable", () => {
  const source = dataset.sources.find((item) => item.id === PUBLIC_ID);
  assert.deepEqual(filterSources([source], { query: "Teatro Condell" }), [source]);
  assert.deepEqual(filterSources([source], { query: "Insomnia Cine" }), [source]);
});
