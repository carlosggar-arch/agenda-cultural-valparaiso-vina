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
    import(new URL("./favorites-event-page.js?v=20260817", scriptUrl).href)
      .catch((error) => console.warn("Agenda Cultural: favoritos no disponibles en esta ficha", error));
  }
})();
