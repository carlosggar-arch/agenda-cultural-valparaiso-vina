const nativeFetch = globalThis.fetch.bind(globalThis);
const REGISTRY_URL = new URL("./cities.json", import.meta.url).href;
let datasetConfigPromise = null;

function requestUrl(input) {
  try {
    const raw = input instanceof Request ? input.url : String(input || "");
    return new URL(raw, document.baseURI).href;
  } catch {
    return "";
  }
}

function canonicalLink(event) {
  const value = event?.links?.official || event?.links?.source || event?.source_url;
  if (!value) return "";
  try {
    const url = new URL(String(value), document.baseURI);
    url.hash = "";
    return url.href.replace(/\/$/, "");
  } catch {
    return String(value).trim().replace(/\/$/, "");
  }
}

async function datasetConfig() {
  if (!datasetConfigPromise) {
    datasetConfigPromise = nativeFetch(REGISTRY_URL, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    })
      .then((response) => {
        if (!response.ok) throw new Error(`city registry HTTP ${response.status}`);
        return response.json();
      })
      .then((registry) => {
        const map = new Map();
        for (const city of registry?.cities || []) {
          if (!city?.dataset || !city?.supplemental_dataset) continue;
          const dataset = new URL(city.dataset, document.baseURI).href;
          const supplemental = new URL(city.supplemental_dataset, document.baseURI).href;
          map.set(dataset, supplemental);
        }
        return map;
      })
      .catch((error) => {
        console.warn("Agenda Cultural: no se pudo leer la configuración de eventos suplementarios", error);
        return new Map();
      });
  }
  return datasetConfigPromise;
}

function mergeEvents(baseEvents, supplementalEvents) {
  const merged = [...(Array.isArray(baseEvents) ? baseEvents : [])];
  const ids = new Set(merged.map((event) => String(event?.id || "").trim()).filter(Boolean));
  const links = new Set(merged.map(canonicalLink).filter(Boolean));

  for (const event of Array.isArray(supplementalEvents) ? supplementalEvents : []) {
    const id = String(event?.id || "").trim();
    const link = canonicalLink(event);
    if ((id && ids.has(id)) || (link && links.has(link))) continue;
    merged.push(event);
    if (id) ids.add(id);
    if (link) links.add(link);
  }
  return merged;
}

function withMergedCounts(payload, events, baseLength) {
  const added = Math.max(0, events.length - baseLength);
  if (!added || !payload?.counts || typeof payload.counts !== "object") return payload?.counts;
  const counts = { ...payload.counts };
  if (Number.isFinite(Number(counts.total))) counts.total = Number(counts.total) + added;
  if (Number.isFinite(Number(counts.events))) counts.events = Number(counts.events) + added;
  return counts;
}

globalThis.fetch = async function agendaFetchWithSupplementalEvents(input, init) {
  const response = await nativeFetch(input, init);
  const url = requestUrl(input);
  if (!response.ok || !url || !/agenda_web\.json(?:$|[?#])/u.test(url)) return response;

  const config = await datasetConfig();
  const supplementalUrl = config.get(url);
  if (!supplementalUrl) return response;

  try {
    const [basePayload, supplementalResponse] = await Promise.all([
      response.clone().json(),
      nativeFetch(supplementalUrl, {
        headers: { Accept: "application/json" },
        cache: "no-store",
      }),
    ]);
    if (!supplementalResponse.ok) return response;
    const supplementalPayload = await supplementalResponse.json();
    if (!Array.isArray(basePayload?.events) || !Array.isArray(supplementalPayload?.events)) return response;

    const events = mergeEvents(basePayload.events, supplementalPayload.events);
    if (events.length === basePayload.events.length) return response;

    const payload = {
      ...basePayload,
      events,
      counts: withMergedCounts(basePayload, events, basePayload.events.length),
    };
    return new Response(JSON.stringify(payload), {
      status: response.status,
      statusText: response.statusText,
      headers: { "Content-Type": "application/json; charset=utf-8" },
    });
  } catch (error) {
    console.warn("Agenda Cultural: no se pudieron combinar eventos suplementarios", error);
    return response;
  }
};
