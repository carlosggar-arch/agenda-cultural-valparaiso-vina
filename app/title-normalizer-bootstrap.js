import { normalizePublicEventTitle } from "./public-title-normalizer.mjs?v=20260818-title3";

const upstreamFetch = window.fetch.bind(window);

function normalizeDataset(dataset) {
  if (!dataset || !Array.isArray(dataset.events)) return dataset;
  return {
    ...dataset,
    events: dataset.events.map((event) => ({
      ...event,
      title: normalizePublicEventTitle(event?.title || "", event) || event?.title || "Actividad sin título",
    })),
  };
}

window.fetch = async (...args) => {
  const response = await upstreamFetch(...args);
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("json")) return response;

  try {
    const dataset = await response.clone().json();
    if (!dataset || !Array.isArray(dataset.events)) return response;
    const normalized = normalizeDataset(dataset);
    const headers = new Headers(response.headers);
    headers.delete("content-length");
    return new Response(JSON.stringify(normalized), {
      status: response.status,
      statusText: response.statusText,
      headers,
    });
  } catch {
    return response;
  }
};
