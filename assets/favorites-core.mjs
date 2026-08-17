import { isSafeCityId, normalizeCityId } from "./city-registry.mjs?v=20260817-city-registry";

export const FAVORITES_STORAGE_KEY = "agenda-cultural-favorites-v1";
export const FAVORITES_CHANGED_EVENT = "agenda-cultural-favorites-changed";

function text(value) {
  return String(value ?? "").trim();
}

function currentStorage(storage) {
  if (storage) return storage;
  try { return window.localStorage; } catch { return null; }
}

function safeHttpUrl(value) {
  const candidate = text(value);
  return /^https?:\/\//i.test(candidate) ? candidate : null;
}

export function favoriteKey(city, id) {
  const normalizedCity = normalizeCityId(city);
  const normalizedId = text(id);
  if (!isSafeCityId(normalizedCity) || !normalizedId) return null;
  return `${normalizedCity}:${normalizedId}`;
}

export function normalizeFavorite(value) {
  if (!value || typeof value !== "object") return null;
  const city = normalizeCityId(value.city);
  const id = text(value.id);
  const key = favoriteKey(city, id);
  if (!key) return null;
  const savedAtCandidate = text(value.savedAt);
  const savedAt = Number.isNaN(Date.parse(savedAtCandidate)) ? new Date(0).toISOString() : new Date(savedAtCandidate).toISOString();
  return {
    city,
    id,
    title: text(value.title) || "Actividad guardada",
    url: safeHttpUrl(value.url),
    savedAt,
  };
}

export function loadFavorites(storage = null) {
  const target = currentStorage(storage);
  if (!target) return [];
  let parsed;
  try { parsed = JSON.parse(target.getItem(FAVORITES_STORAGE_KEY) || "[]"); } catch { return []; }
  if (!Array.isArray(parsed)) return [];
  const byKey = new Map();
  for (const raw of parsed) {
    const favorite = normalizeFavorite(raw);
    const key = favorite && favoriteKey(favorite.city, favorite.id);
    if (!favorite || !key) continue;
    const previous = byKey.get(key);
    if (!previous || favorite.savedAt >= previous.savedAt) byKey.set(key, favorite);
  }
  return [...byKey.values()].sort((left, right) => right.savedAt.localeCompare(left.savedAt));
}

export function writeFavorites(favorites, storage = null) {
  const target = currentStorage(storage);
  if (!target) return false;
  const normalized = [];
  const seen = new Set();
  for (const raw of favorites || []) {
    const favorite = normalizeFavorite(raw);
    const key = favorite && favoriteKey(favorite.city, favorite.id);
    if (!favorite || !key || seen.has(key)) continue;
    seen.add(key);
    normalized.push(favorite);
  }
  try {
    target.setItem(FAVORITES_STORAGE_KEY, JSON.stringify(normalized));
    return true;
  } catch {
    return false;
  }
}

export function isFavorite(city, id, storage = null) {
  const key = favoriteKey(city, id);
  if (!key) return false;
  return loadFavorites(storage).some((item) => favoriteKey(item.city, item.id) === key);
}

export function saveFavorite(value, storage = null) {
  const favorite = normalizeFavorite({ ...value, savedAt: value?.savedAt || new Date().toISOString() });
  if (!favorite) return { saved: false, favorite: null, favorites: loadFavorites(storage) };
  const key = favoriteKey(favorite.city, favorite.id);
  const next = loadFavorites(storage).filter((item) => favoriteKey(item.city, item.id) !== key);
  next.unshift(favorite);
  const saved = writeFavorites(next, storage);
  return { saved, favorite, favorites: saved ? next : loadFavorites(storage) };
}

export function removeFavorite(city, id, storage = null) {
  const key = favoriteKey(city, id);
  const current = loadFavorites(storage);
  if (!key) return { removed: false, favorites: current };
  const next = current.filter((item) => favoriteKey(item.city, item.id) !== key);
  const removed = next.length !== current.length;
  if (removed) writeFavorites(next, storage);
  return { removed, favorites: removed ? next : current };
}

export function toggleFavorite(value, storage = null) {
  const favorite = normalizeFavorite({ ...value, savedAt: value?.savedAt || new Date().toISOString() });
  if (!favorite) return { active: false, changed: false, favorite: null, favorites: loadFavorites(storage) };
  if (isFavorite(favorite.city, favorite.id, storage)) {
    const result = removeFavorite(favorite.city, favorite.id, storage);
    return { active: false, changed: result.removed, favorite, favorites: result.favorites };
  }
  const result = saveFavorite(favorite, storage);
  return { active: result.saved, changed: result.saved, favorite, favorites: result.favorites };
}

export function emitFavoritesChanged(detail = {}) {
  try {
    if (typeof window !== "undefined" && typeof window.dispatchEvent === "function") {
      window.dispatchEvent(new CustomEvent(FAVORITES_CHANGED_EVENT, { detail }));
    }
  } catch {}
}

export function favoritesForCity(city, storage = null) {
  const normalizedCity = normalizeCityId(city);
  return loadFavorites(storage).filter((item) => item.city === normalizedCity);
}
