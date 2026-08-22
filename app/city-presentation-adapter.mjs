import { gijonLocationForEvent, scheduleForGijonEvent } from "./gijon-venue-hours.js?v=20260820-hours1";

function fold(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .trim();
}

function safeAbsoluteHttpUrl(value) {
  try {
    const url = new URL(String(value || ""));
    return ["http:", "https:"].includes(url.protocol) ? url : null;
  } catch {
    return null;
  }
}

function presentationLocationForGijon(event) {
  const location = gijonLocationForEvent(event);
  const venue = fold(location?.venue);
  if (["gijon/xixon", "gijon", "xixon"].includes(venue)) {
    // A city name used as a venue is a source placeholder, not a useful public
    // location. Remove it at the adapter boundary so every common renderer
    // naturally falls back to “Lugar por confirmar”.
    return { ...location, venue: "", city: "" };
  }
  return location;
}

function browserFriendlyGijonUrl(value) {
  const url = safeAbsoluteHttpUrl(value);
  if (!url) return null;
  if (url.hostname.toLocaleLowerCase("es") === "opendata.gijon.es" && url.pathname.endsWith("/descargar.php")) {
    const type = String(url.searchParams.get("tipo") || "").toLocaleUpperCase("es");
    if (type === "XHTML") url.searchParams.set("tipo", "PDF");
  }
  return url.href;
}

function isMainGijonMunicipalAlias(value) {
  const url = safeAbsoluteHttpUrl(value);
  if (!url) return false;
  const host = url.hostname.toLocaleLowerCase("es");
  return host === "gijon.es" || host === "www.gijon.es";
}

function presentationLinksForGijon(event) {
  const links = { ...(event?.links || {}) };
  const quality = String(event?.public_status?.external_link_quality || "");
  const isOpenData = String(event?.source_id || "") === "gijon_opendata_events";
  const corroborating = links.corroborating || links.verified_source || links.secondary_source;

  let preferred = corroborating || links.official || links.source || event?.source_url || null;
  if (!corroborating && isOpenData && quality === "opendata_fallback") {
    preferred = links.source || event?.source_url || links.official;
  } else if (!corroborating && isOpenData && isMainGijonMunicipalAlias(links.official) && quality !== "direct_official") {
    preferred = links.source || event?.source_url || links.official;
  }

  const browserFriendly = browserFriendlyGijonUrl(preferred);
  if (!browserFriendly) return { links, sourceUrl: event?.source_url || null };
  return {
    links: {
      ...links,
      official: browserFriendly,
      presentation_source: browserFriendly,
    },
    sourceUrl: browserFriendly,
  };
}

export function eventForCityPresentation(event, cityId) {
  if (!event || typeof event !== "object") return event;
  if (cityId !== "gijon") return event;
  const source = presentationLinksForGijon(event);
  return {
    ...event,
    location: presentationLocationForGijon(event),
    schedule: scheduleForGijonEvent(event),
    links: source.links,
    source_url: source.sourceUrl,
  };
}

export function venueHoursForCity(event, cityId) {
  if (!event || typeof event !== "object") return null;
  void cityId;
  // Group headers must not repeat a weekly/seasonal venue schedule because the
  // card represents one concrete viewing date. Date-specific visit hours are
  // rendered later from structured schedule data by the shared presentation
  // layer; when that cannot be determined reliably, showing no hours is safer.
  return null;
}
