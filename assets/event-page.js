(() => {
  const scriptUrl = document.currentScript?.src || null;
  const status = document.querySelector("[data-share-status]");
  const setStatus = (message) => {
    if (!status) return;
    status.textContent = message;
    window.clearTimeout(setStatus.timer);
    setStatus.timer = window.setTimeout(() => { status.textContent = ""; }, 3500);
  };

  const heroImage = document.querySelector(".event-hero-media img");
  const removeBrokenHero = () => {
    const media = heroImage?.closest(".event-hero-media");
    const sheet = heroImage?.closest(".event-sheet");
    media?.remove();
    sheet?.classList.add("event-sheet--no-media");
  };
  if (heroImage) {
    heroImage.addEventListener("error", removeBrokenHero, { once: true });
    if (heroImage.complete && heroImage.naturalWidth === 0) removeBrokenHero();
  }

  function safeHttpUrl(value) {
    if (!value) return null;
    try {
      const url = new URL(String(value), window.location.href);
      return ["http:", "https:"].includes(url.protocol) ? url.href : null;
    } catch {
      return null;
    }
  }

  function isGijonOpenDataUrl(value) {
    const url = safeHttpUrl(value);
    return Boolean(url && new URL(url).hostname.toLowerCase() === "opendata.gijon.es");
  }

  async function replaceGijonOpenDataLinks() {
    if (document.body?.dataset.city !== "gijon" || !scriptUrl) return;
    const openDataLinks = [...document.querySelectorAll('a[href*="opendata.gijon.es"]')];
    if (!openDataLinks.length) return;

    const eventId = String(document.body.dataset.eventId || "").trim();
    if (!eventId) return;

    let corroborating = null;
    try {
      const datasetUrl = new URL("../app/data/gijon/agenda_web.json", scriptUrl);
      const response = await fetch(datasetUrl, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      const event = (payload.events || []).find((candidate) => String(candidate?.id || "") === eventId);
      const municipal = safeHttpUrl(event?.links?.municipal_page);
      const official = safeHttpUrl(event?.links?.official);
      if (municipal && !isGijonOpenDataUrl(municipal)) corroborating = municipal;
      else if (official && !isGijonOpenDataUrl(official)) corroborating = official;
    } catch (error) {
      console.warn("Agenda Cultural: no se pudo cargar la fuente corroborante de Gijón", error);
    }

    for (const link of openDataLinks) {
      if (corroborating) {
        link.href = corroborating;
        link.textContent = link.closest(".event-facts")
          ? "Ayuntamiento de Gijón/Xixón — ficha específica del evento ↗"
          : "Fuente oficial ↗";
      } else {
        const replacement = document.createElement("span");
        replacement.textContent = "Fuente específica pendiente de corroborar";
        link.replaceWith(replacement);
      }
    }
  }

  void replaceGijonOpenDataLinks();

  document.querySelector("[data-native-share]")?.addEventListener("click", async () => {
    const data = { title: document.title.replace(/ · Agenda Cultural$/, ""), url: window.location.href };
    if (!navigator.share) {
      try {
        await navigator.clipboard.writeText(window.location.href);
        setStatus("Enlace copiado");
      } catch {
        setStatus("Copia el enlace desde la barra del navegador");
      }
      return;
    }
    try {
      await navigator.share(data);
      setStatus("Compartido");
    } catch (error) {
      if (error?.name !== "AbortError") setStatus("No se pudo compartir");
    }
  });

  document.querySelector("[data-copy-link]")?.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setStatus("Enlace copiado");
    } catch {
      setStatus("Copia el enlace desde la barra del navegador");
    }
  });

  if (scriptUrl) {
    import(new URL("./usage-analytics.js?v=20260817-stage32", scriptUrl).href)
      .catch(() => {});
    import(new URL("./favorites-event-page.js?v=20260817", scriptUrl).href)
      .catch((error) => console.warn("Agenda Cultural: favoritos no disponibles en esta ficha", error));
  }
})();
