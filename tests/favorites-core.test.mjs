import assert from "node:assert/strict";
import test from "node:test";

import {
  FAVORITES_STORAGE_KEY,
  favoriteKey,
  favoritesForCity,
  isFavorite,
  loadFavorites,
  normalizeFavorite,
  removeFavorite,
  saveFavorite,
  toggleFavorite,
} from "../assets/favorites-core.mjs";

function memoryStorage(initial = {}) {
  const data = new Map(Object.entries(initial));
  return {
    getItem(key) { return data.has(key) ? data.get(key) : null; },
    setItem(key, value) { data.set(key, String(value)); },
    removeItem(key) { data.delete(key); },
  };
}

test("favorite keys are city-scoped", () => {
  assert.equal(favoriteKey("valparaiso", "abc"), "valparaiso:abc");
  assert.equal(favoriteKey("gijon", "abc"), "gijon:abc");
  assert.equal(favoriteKey("unknown", "abc"), null);
});

test("saving and toggling persist favorites in browser-like storage", () => {
  const storage = memoryStorage();
  const favorite = {
    city: "valparaiso",
    id: "evento-1",
    title: "Mi concierto",
    url: "https://example.org/evento-1",
    savedAt: "2026-08-17T16:00:00Z",
  };

  const saved = saveFavorite(favorite, storage);
  assert.equal(saved.saved, true);
  assert.equal(isFavorite("valparaiso", "evento-1", storage), true);
  assert.equal(loadFavorites(storage)[0].title, "Mi concierto");

  const toggled = toggleFavorite(favorite, storage);
  assert.equal(toggled.active, false);
  assert.equal(isFavorite("valparaiso", "evento-1", storage), false);
});

test("favorites remain independent between Valparaiso and Gijon", () => {
  const storage = memoryStorage();
  saveFavorite({ city: "valparaiso", id: "same", title: "Valpo", savedAt: "2026-08-17T16:00:00Z" }, storage);
  saveFavorite({ city: "gijon", id: "same", title: "Gijón", savedAt: "2026-08-17T16:01:00Z" }, storage);

  assert.equal(loadFavorites(storage).length, 2);
  assert.equal(favoritesForCity("valparaiso", storage).length, 1);
  assert.equal(favoritesForCity("gijon", storage).length, 1);
  removeFavorite("valparaiso", "same", storage);
  assert.equal(isFavorite("gijon", "same", storage), true);
});

test("corrupt storage and duplicate records fail safely", () => {
  const corrupt = memoryStorage({ [FAVORITES_STORAGE_KEY]: "not-json" });
  assert.deepEqual(loadFavorites(corrupt), []);

  const duplicate = memoryStorage({
    [FAVORITES_STORAGE_KEY]: JSON.stringify([
      { city: "valparaiso", id: "x", title: "Old", savedAt: "2026-08-17T10:00:00Z" },
      { city: "valparaiso", id: "x", title: "New", savedAt: "2026-08-17T11:00:00Z" },
      { city: "invalid", id: "z", title: "Ignored", savedAt: "2026-08-17T12:00:00Z" },
    ]),
  });
  const values = loadFavorites(duplicate);
  assert.equal(values.length, 1);
  assert.equal(values[0].title, "New");
});

test("normalization rejects unusable entries and unsafe urls", () => {
  assert.equal(normalizeFavorite({ city: "valparaiso", id: "" }), null);
  const normalized = normalizeFavorite({ city: "gijon", id: "1", title: "Plan", url: "javascript:alert(1)", savedAt: "bad" });
  assert.ok(normalized);
  assert.equal(normalized.url, null);
  assert.equal(normalized.savedAt, new Date(0).toISOString());
});
