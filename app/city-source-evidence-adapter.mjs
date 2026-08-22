const VERIFIED_GIJON_EVENT_PAGES = Object.freeze({
  "https://www.gijon.es/nunca-es-tarde-para-pintar": Object.freeze({
    sourceName: "Ayuntamiento de Gijón/Xixón",
  }),
  "https://www.gijon.es/exposicion-mientras-tu-dormias": Object.freeze({
    sourceName: "Ayuntamiento de Gijón/Xixón",
    openingTime: "09:00",
    closingTime: "21:00",
  }),
});

function safeAbsoluteHttpUrl(value) {
  try {
    const url = new URL(String(value || ""));
    return ["http:", "https:"].includes(url.protocol) ? url : null;
  } catch {
    return null;
  }
}

function normalizedPublicUrl(value) {
  const url = safeAbsoluteHttpUrl(value);
  if (!url) return null;
  url.hash = "";
  url.search = "";
  return url.href.replace(/\/$/, "");
}

function verifiedGijonEventPage(event) {
  const pageUrl = normalizedPublicUrl(event?.links?.municipal_page);
  if (!pageUrl) return null;
  const spec = VERIFIED_GIJON_EVENT_PAGES[pageUrl];
  return spec ? { ...spec, url: pageUrl } : null;
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

function preferredGijonEvidence(event) {
  const links = event?.links || {};
  const quality = String(event?.public_status?.external_link_quality || "");
  const isOpenData = String(event?.source_id || "") === "gijon_opendata_events";
  const verified = verifiedGijonEventPage(event);
  const corroborating = verified?.url || links.corroborating || links.verified_source || links.secondary_source;

  let preferred = corroborating || links.official || links.source || event?.source_url || null;
  if (!corroborating && isOpenData && quality === "opendata_fallback") {
    preferred = links.source || event?.source_url || links.official;
  } else if (!corroborating && isOpenData && isMainGijonMunicipalAlias(links.official) && quality !== "direct_official") {
    preferred = links.source || event?.source_url || links.official;
  }

  const url = browserFriendlyGijonUrl(preferred);
  if (!url) return null;
  return {
    url,
    role: corroborating ? "official" : "institutional",
    source_kind: corroborating ? "official" : "institutional",
    source_id: event?.source_id || null,
    source_name: verified?.sourceName || event?.source_name || event?.organizer || null,
    presentation_preferred: true,
    evidence_origin: verified ? "verified_event_page" : corroborating ? "corroborating_link" : "gijon_public_fallback",
  };
}

export function enrichCitySourceEvidence(event, cityId) {
  if (!event || typeof event !== "object" || cityId !== "gijon") return event;
  const preferred = preferredGijonEvidence(event);
  if (!preferred) return event;
  const existing = Array.isArray(event.source_evidence) ? event.source_evidence : [];
  const normalizedPreferred = String(preferred.url || "").replace(/\/$/, "");
  const withoutDuplicate = existing.filter((item) => String(item?.url || "").replace(/\/$/, "") !== normalizedPreferred);
  return {
    ...event,
    source_evidence: [...withoutDuplicate, preferred],
  };
}

export { browserFriendlyGijonUrl, verifiedGijonEventPage };
