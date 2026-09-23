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

function sourceNameForDestination(event, value, verified) {
  if (verified?.sourceName) return verified.sourceName;
  const url = safeAbsoluteHttpUrl(value);
  const source = safeAbsoluteHttpUrl(event?.source_url || event?.links?.source);
  const name = String(event?.source_name || event?.organizer || "").trim();
  if (!url) return null;
  const host = url.hostname.toLowerCase().replace(/^www\./u, "");
  if (host === "opendata.gijon.es") return "Open Data Ayuntamiento de Gijón/Xixón";
  if (host === "gijon.es" || host.endsWith(".gijon.es")) return "Ayuntamiento de Gijón/Xixón";
  const inheritedOpenData = event?.source_id === "gijon_opendata_events"
    || /open\s*data/iu.test(name)
    || source?.hostname === "opendata.gijon.es";
  // The ingestion feed's label must never describe a different destination.
  // A domain is an exact label when the feed does not supply its publisher.
  return inheritedOpenData ? host : name || host;
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
    source_name: sourceNameForDestination(event, url, verified),
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
