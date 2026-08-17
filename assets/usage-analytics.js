(() => {
  const ENDPOINT = "https://agenda-cultural-community.carlosggar.workers.dev/community/v1/analytics/events";
  const PUBLIC_ORIGIN = "https://carlosggar-arch.github.io";
  const disabled = location.origin !== PUBLIC_ORIGIN || navigator.globalPrivacyControl === true || navigator.doNotTrack === "1" || window.doNotTrack === "1";
  const queue = [];
  let timer = 0;
  let appOpenSent = false;
  const searchTimers = new WeakMap();

  const currentCity = () => {
    const dataCity = document.documentElement.dataset.city || document.body?.dataset.city;
    if (dataCity === "gijon" || dataCity === "valparaiso") return dataCity;
    if (/\/gijon\//.test(location.pathname) || /\/evento\/gijon\//.test(location.pathname)) return "gijon";
    return "valparaiso";
  };

  const eventIdFor = (node) => {
    const candidate = node?.closest?.("[data-event-id]")?.dataset.eventId || document.body?.dataset.eventId || "";
    return /^[A-Za-z0-9._:-]{3,180}$/.test(candidate) ? candidate : "";
  };

  const cleanToken = (value, max = 80) => {
    const text = String(value ?? "").normalize("NFKC").trim().toLocaleLowerCase("es").slice(0, max);
    return /^[a-z0-9áéíóúüñ._:-]*$/i.test(text) ? text : "";
  };

  const flush = () => {
    if (disabled || !queue.length) return;
    window.clearTimeout(timer); timer = 0;
    const events = queue.splice(0, 20);
    fetch(ENDPOINT, {
      method: "POST",
      mode: "cors",
      credentials: "omit",
      referrerPolicy: "no-referrer",
      keepalive: true,
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ events }),
    }).catch(() => {}).finally(() => {
      if (queue.length) timer = window.setTimeout(flush, 700);
    });
  };

  const track = (event, options = {}) => {
    if (disabled) return;
    const item = {
      event: cleanToken(event, 40),
      city: currentCity(),
      dimension: cleanToken(options.dimension || "", 30),
      value: cleanToken(options.value || "", 80),
      event_id: eventIdFor(options.node || null),
    };
    if (!item.event) return;
    queue.push(item);
    if (queue.length >= 10) flush();
    else if (!timer) timer = window.setTimeout(flush, 700);
  };

  const sendInitialView = () => {
    if (disabled) return;
    if (document.body?.dataset.eventPage !== undefined) {
      track("event_open", { dimension: "surface", value: "permalink", node: document.body });
      return;
    }
    if (/\/app\/?$/.test(location.pathname) || location.pathname.endsWith("/app/")) {
      const discovery = document.querySelector("[data-discovery]");
      const send = () => {
        if (appOpenSent || discovery?.hidden !== false) return;
        appOpenSent = true;
        track("app_open", { dimension: "surface", value: "pwa" });
      };
      send();
      if (discovery && !appOpenSent) new MutationObserver(send).observe(discovery, { attributes: true, attributeFilter: ["hidden"] });
      return;
    }
    track("landing_view", { dimension: "surface", value: currentCity() === "gijon" ? "city-landing" : "root" });
  };

  document.addEventListener("click", (event) => {
    if (disabled) return;
    const target = event.target instanceof Element ? event.target : null;
    if (!target) return;
    const city = target.closest("[data-city-option]");
    if (city) track("city_select", { dimension: "city", value: city.dataset.cityOption });

    const when = target.closest("[data-combined-when] [data-filter-value]");
    if (when) track("filter_use", { dimension: "when", value: when.dataset.filterValue });
    const area = target.closest("[data-combined-area] [data-filter-value]");
    if (area) track("filter_use", { dimension: "area", value: area.dataset.filterValue });
    const category = target.closest("[data-combined-category]");
    if (category) track("filter_use", { dimension: "category", value: category.dataset.combinedCategory });

    const share = target.closest("[data-native-share], [data-copy-link]");
    if (share) track("share", { dimension: "action", value: share.matches("[data-native-share]") ? "native" : "copy", node: share });

    const anchor = target.closest("a[href]");
    if (!anchor) return;
    let href;
    try { href = new URL(anchor.href, location.href); } catch { return; }
    const node = anchor.closest("[data-event-id]") || document.body;
    if (/evento\.ics(?:$|\?)/.test(href.pathname + href.search) || href.hostname === "calendar.google.com") {
      track("calendar_download", { dimension: "action", value: href.hostname === "calendar.google.com" ? "google" : "ics", node });
      return;
    }
    if (href.origin !== location.origin && eventIdFor(node)) {
      track("outbound_open", { dimension: "action", value: "external", node });
    }
  }, true);

  document.addEventListener("change", (event) => {
    if (disabled) return;
    const target = event.target instanceof Element ? event.target : null;
    if (!target) return;
    if (target.matches("[data-filter-period]")) track("filter_use", { dimension: "when", value: target.value || "todos" });
    if (target.matches("[data-filter-city]")) track("filter_use", { dimension: "city", value: target.value || "todos" });
    if (target.matches("[data-filter-category]")) track("filter_use", { dimension: "category", value: target.value || "todos" });
    if (target.matches("[data-filter-free]")) track("filter_use", { dimension: "category", value: target.checked ? "gratis" : "todos" });
    if (target.matches("[data-filter-workshops]")) track("filter_use", { dimension: "category", value: target.checked ? "talleres-flexibles" : "todos" });
    if (target.matches("[data-date-from], [data-date-to]")) track("filter_use", { dimension: "when", value: "personalizado" });
  }, true);

  document.addEventListener("input", (event) => {
    if (disabled) return;
    const input = event.target instanceof HTMLInputElement ? event.target : null;
    if (!input?.matches("[data-smart-search], [data-filter-query]")) return;
    window.clearTimeout(searchTimers.get(input));
    const handle = window.setTimeout(() => {
      const length = input.value.trim().length;
      if (length < 2) return;
      const bucket = length <= 4 ? "2-4" : length <= 9 ? "5-9" : "10plus";
      track("search_use", { dimension: "search_length", value: bucket });
    }, 900);
    searchTimers.set(input, handle);
  }, true);

  window.addEventListener("appinstalled", () => track("app_install", { dimension: "surface", value: "pwa" }));
  document.addEventListener("visibilitychange", () => { if (!disabled && document.visibilityState === "hidden") flush(); });
  window.addEventListener("pagehide", flush);
  window.AgendaUsageAnalytics = Object.freeze({ track, flush, disabled });

  if (!disabled) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", sendInitialView, { once: true });
    else sendInitialView();
  }
})();
