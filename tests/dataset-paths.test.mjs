import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../assets/agenda.js", import.meta.url), "utf8");

test("GitHub Pages loads datasets from the repository base path", () => {
  assert.match(source, /const DATASET_PATH = "\.\/agenda_web\.json";/);
  assert.match(source, /const CHANGES_PATH = "\.\/agenda_changes\.json";/);
  assert.doesNotMatch(source, /\.\.\/agenda_(?:web|changes)\.json/);
});
