(() => {
  const originalFetch = window.fetch.bind(window);
  const BLOCKED_EVENT_IDS = new Set([
    "agenda_968c623b60b70d2976410175",
  ]);

  function normalized(value) {
    return String(value ?? "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLocaleLowerCase("es")
      .replace(/\s+/g, " ")
      .trim();
  }

  function sourceUrl(event) {
    return String(event?.source_url || event?.links?.source || event?.links?.official || "");
  }

  function lacksStructuredEventEvidence(event) {
    return !String(event?.location?.venue || "").trim()
      && !String(event?.organizer || "").trim()
      && !String(event?.links?.tickets || "").trim()
      && !String(event?.links?.registration || "").trim();
  }

  function isEditorialInstagramFalsePositive(event) {
    if (BLOCKED_EVENT_IDS.has(String(event?.id || ""))) return true;
    if (!sourceUrl(event).includes("instagram.com/")) return false;
    if (!lacksStructuredEventEvidence(event)) return false;

    const title = normalized(event?.title);
    const description = normalized(event?.description);
    const editorialCue = title.startsWith("¿sabias")
      || title.startsWith("sabias")
      || description.includes("te contamos curiosidades")
      || description.includes("curiosidades y detalles");

    return editorialCue;
  }

  function refreshCounts(dataset) {
    if (!dataset?.counts || !Array.isArray(dataset.events)) return;
    const events = dataset.events;
    dataset.counts.total = events.length;
    dataset.counts.events = events.filter((event) => event?.event_type === "event").length;
    dataset.counts.courses = events.filter((event) => event?.event_type === "course").length;
    dataset.counts.flexible_offers = events.filter((event) => event?.event_type === "flexible_offer").length;
    dataset.counts.programs = events.filter((event) => event?.event_type === "program").length;
  }

  window.fetch = async (...args) => {
    const response = await originalFetch(...args);
    const request = args[0];
    const url = typeof request === "string" ? request : request?.url || "";
    if (!/agenda_web\.json(?:[?#]|$)/.test(url) || !response.ok) return response;

    try {
      const dataset = await response.clone().json();
      if (!Array.isArray(dataset?.events)) return response;
      const filtered = dataset.events.filter((event) => !isEditorialInstagramFalsePositive(event));
      if (filtered.length === dataset.events.length) return response;

      dataset.events = filtered;
      refreshCounts(dataset);
      const headers = new Headers(response.headers);
      headers.set("Content-Type", "application/json; charset=utf-8");
      headers.delete("Content-Length");
      headers.delete("Content-Encoding");
      return new Response(JSON.stringify(dataset), {
        status: response.status,
        statusText: response.statusText,
        headers,
      });
    } catch {
      return response;
    }
  };
})();