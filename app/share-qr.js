const SHARE_URL = "https://carlosggar-arch.github.io/agenda-cultural-valparaiso-vina/app/";
const SHARE_TITLE = "¡Vivamos!";
const SHARE_TEXT = "Descubre la agenda cultural y compártela con otras personas.";

function installShareStyles() {
  if (document.querySelector('link[data-share-qr-styles]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = "./share-qr.css";
  link.dataset.shareQrStyles = "true";
  document.head.append(link);
}

function ensureShareButton() {
  const headerActions = document.querySelector(".header-actions");
  if (!headerActions) return null;

  let button = headerActions.querySelector("[data-share-qr-open]");
  if (button) return button;

  button = document.createElement("button");
  button.type = "button";
  button.className = "share-qr-button";
  button.dataset.shareQrOpen = "true";
  button.setAttribute("aria-label", "Compartir aplicación");
  button.title = "Compartir aplicación";
  button.innerHTML = '<img src="./icons/share-qr-app.svg" width="20" height="20" alt="" aria-hidden="true">';

  const citySwitch = headerActions.querySelector("[data-city-switch]");
  if (citySwitch) headerActions.insertBefore(button, citySwitch);
  else headerActions.append(button);
  return button;
}

function ensureShareDialog() {
  let backdrop = document.querySelector("[data-share-qr-backdrop]");
  if (backdrop) return backdrop;

  backdrop = document.createElement("div");
  backdrop.className = "chooser-backdrop share-qr-backdrop";
  backdrop.dataset.shareQrBackdrop = "true";
  backdrop.hidden = true;
  backdrop.innerHTML = `
    <section class="chooser share-qr-panel" role="dialog" aria-modal="true" aria-labelledby="share-qr-title">
      <button class="chooser-close" type="button" aria-label="Cerrar" data-share-qr-close>×</button>
      <p class="eyebrow">¡Vivamos!</p>
      <h2 id="share-qr-title">Compartir la aplicación</h2>
      <p>Escanea el código o comparte el enlace para abrir ¡Vivamos! en cualquier móvil.</p>
      <div class="share-qr-preview">
        <img src="./icons/share-qr-app.svg" alt="Código QR para abrir la aplicación ¡Vivamos!" width="220" height="220">
      </div>
      <p class="share-qr-link">${SHARE_URL}</p>
      <div class="share-qr-actions">
        <button class="share-qr-action" type="button" data-share-native>Compartir</button>
        <button class="share-qr-action share-qr-action-secondary" type="button" data-share-copy>Copiar enlace</button>
      </div>
      <p class="chooser-message share-qr-feedback" data-share-qr-feedback aria-live="polite"></p>
    </section>`;
  document.body.append(backdrop);

  const close = () => {
    backdrop.hidden = true;
    document.querySelector("[data-share-qr-open]")?.focus?.();
  };

  backdrop.querySelector("[data-share-qr-close]")?.addEventListener("click", close);
  backdrop.addEventListener("click", (event) => {
    if (event.target === backdrop) close();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !backdrop.hidden) close();
  });

  backdrop.querySelector("[data-share-native]")?.addEventListener("click", async () => {
    const feedback = backdrop.querySelector("[data-share-qr-feedback]");
    if (!navigator.share) {
      feedback.textContent = "Tu navegador no permite compartir directamente. Puedes copiar el enlace.";
      return;
    }
    try {
      await navigator.share({ title: SHARE_TITLE, text: SHARE_TEXT, url: SHARE_URL });
      feedback.textContent = "Aplicación compartida.";
    } catch (error) {
      if (error?.name === "AbortError") return;
      feedback.textContent = "No se pudo abrir el menú para compartir. Prueba copiando el enlace.";
    }
  });

  backdrop.querySelector("[data-share-copy]")?.addEventListener("click", async () => {
    const feedback = backdrop.querySelector("[data-share-qr-feedback]");
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(SHARE_URL);
      } else {
        const helper = document.createElement("textarea");
        helper.value = SHARE_URL;
        helper.setAttribute("readonly", "readonly");
        helper.style.position = "absolute";
        helper.style.left = "-9999px";
        document.body.append(helper);
        helper.select();
        document.execCommand("copy");
        helper.remove();
      }
      feedback.textContent = "Enlace copiado.";
    } catch {
      feedback.textContent = "No se pudo copiar el enlace automáticamente.";
    }
  });

  return backdrop;
}

function openShareDialog() {
  const backdrop = ensureShareDialog();
  const feedback = backdrop.querySelector("[data-share-qr-feedback]");
  if (feedback) feedback.textContent = "";
  backdrop.hidden = false;
  backdrop.querySelector("[data-share-qr-close]")?.focus?.();
}

installShareStyles();
ensureShareButton()?.addEventListener("click", openShareDialog);
ensureShareDialog();
