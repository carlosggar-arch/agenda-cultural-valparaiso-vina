import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const dataset = JSON.parse(await readFile(new URL("../agenda_web.json", import.meta.url), "utf8"));
const byTitle = new Map(dataset.events.map((event) => [event.title.replace(/[“”]/g, ""), event]));

test("official event images survive the complete published dataset", () => {
  const expected = new Map([
    ["Un buen cuento maléfico", "https://www.teatromuseo.cl/images/cartelera/full/mesa-de-trabajo-5-(1)-6a67ef9596392.png"],
    ["Las cumbias que escuchamos allá arriba", "https://www.museobaburizza.cl/wp-content/uploads/2026/07/evento-lascumbias-portada-1.jpg"],
    ["Nebulosa Carina", "https://www.museobaburizza.cl/wp-content/uploads/2026/07/evento-nebulosacarina-portada-1.jpg"],
  ]);
  for (const [title, url] of expected) {
    const event = byTitle.get(title);
    assert.ok(event, `${title} must remain in the canonical dataset`);
    assert.equal(event.image?.url, url, `${title} must preserve its official image`);
    assert.notEqual(event.image?.visual_quality, "text_heavy");
  }
});
