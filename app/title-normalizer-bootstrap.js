import { normalizePublicEventTitle } from "./public-title-normalizer.mjs?v=20260821-title7";

const HASHTAG_TOKEN = /^#[\p{L}\p{N}_-]+$/u;

export function isHashtagOnlyPublicTitle(value) {
  const tokens = String(value || "").trim().split(/\s+/u).filter(Boolean);
  return tokens.length >= 2 && tokens.every((token) => HASHTAG_TOKEN.test(token));
}

export function normalizeAgendaTitles(dataset) {
  if (!dataset || !Array.isArray(dataset.events)) return dataset;
  const events = [];
  for (const event of dataset.events) {
    const rawTitle = event?.title == null ? "" : String(event.title);
    const title = normalizePublicEventTitle(rawTitle, event) || rawTitle || "Actividad sin título";

    // A sequence of social-media hashtags is metadata, not an event title.
    // Do not invent a title from the caption here: conservative publication
    // means the source must provide/recover a semantic title upstream.
    if (isHashtagOnlyPublicTitle(title)) continue;

    const normalized = { ...event, title };
    if (
      event
      && !Object.prototype.hasOwnProperty.call(event, "original_title")
      && rawTitle
      && title !== rawTitle
    ) {
      normalized.original_title = rawTitle;
    }
    events.push(normalized);
  }
  return { ...dataset, events };
}
