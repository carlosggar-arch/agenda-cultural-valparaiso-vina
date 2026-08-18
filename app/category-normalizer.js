const nativeFetch = window.fetch.bind(window);

function slugify(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "cultura";
}

function publicCategory(event) {
  const source = event?.primary_category || event?.categories?.[0] || null;
  let label = String(source?.label || "Actividad cultural").trim() || "Actividad cultural";
  let id = String(source?.id || slugify(label)).trim();
  if (id === "museos" || slugify(label) === "museos") {
    id = "exposiciones";
    label = "Exposiciones";
  } else if (id === "exposiciones") {
    label = "Exposiciones";
  }
  return { id, label };
}

function normalizeAgendaDataset(dataset) {
  if (!dataset || !Array.isArray(dataset.events)) return dataset;
  return {
    ...dataset,
    events: dataset.events.map((event) => {
      const category = publicCategory(event);
      return {
        ...event,
        primary_category: category,
        categories: [category],
      };
    }),
  };
}

window.fetch = async (...args) => {
  const response = await nativeFetch(...args);
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("json")) return response;

  const clone = response.clone();
  try {
    const dataset = await clone.json();
    if (!dataset || !Array.isArray(dataset.events)) return response;
    const normalized = normalizeAgendaDataset(dataset);
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
