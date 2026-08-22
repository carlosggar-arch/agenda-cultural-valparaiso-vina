import { resolveEventImage } from "./image-resolver-core.mjs?v=20260822-single-image1";

function safeHttpUrl(value) {
  if (!value) return null;
  try {
    const url = new URL(String(value), window.location.href);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function addText(parent, tag, className, value) {
  if (value === null || value === undefined || String(value).trim() === "") return null;
  const node = document.createElement(tag);
  if (className) node.className = className;
  node.textContent = String(value);
  parent.append(node);
  return node;
}

function addFact(parent, label, value, icon) {
  if (!value) return;
  const row = document.createElement("div");
  row.className = "event-detail-fact";
  const symbol = addText(row, "span", "event-detail-fact-icon", icon);
  symbol?.setAttribute("aria-hidden", "true");
  const copy = document.createElement("div");
  addText(copy, "strong", "", label);
  addText(copy, "span", "", value);
  row.append(copy);
  parent.append(row);
}

function addExternalAction(parent, href, label, kind = "secondary", { newTab = true } = {}) {
  const safe = safeHttpUrl(href);
  if (!safe) return null;
  const link = document.createElement("a");
  link.className = `event-detail-action event-detail-action--${kind}`;
  link.href = safe;
  if (newTab) {
    link.target = "_blank";
    link.rel = "noopener noreferrer";
  }
  link.textContent = label;
  parent.append(link);
  return link;
}

function addButtonAction(parent, label, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "event-detail-action event-detail-action--secondary";
  button.textContent = label;
  button.addEventListener("click", onClick);
  parent.append(button);
  return button;
}

function dismissDialog(dialog) {
  if (!dialog) return;
  try {
    if (typeof dialog.close === "function" && dialog.hasAttribute("open")) dialog.close();
  } catch (error) {
    console.warn("No se pudo cerrar la ficha de forma nativa", error);
  }
  queueMicrotask(() => {
    if (dialog.isConnected) dialog.remove();
  });
}

async function copyPermanentUrl(value) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value);
      return true;
    }
  } catch {}
  try {
    const input = document.createElement("textarea");
    input.value = value;
    input.setAttribute("readonly", "");
    input.style.position = "fixed";
    input.style.opacity = "0";
    document.body.append(input);
    input.select();
    const copied = document.execCommand?.("copy") === true;
    input.remove();
    return copied;
  } catch {
    return false;
  }
}

function detailDescription(event) {
  const text = String(event?.description || "")
    .replace(/<[^>]+>/g, " ")
    .replace(/\\n/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!text || /^actividad publicada en la agenda/i.test(text)) return null;
  return text;
}

function isGijonOpenDataUrl(value) {
  const safe = safeHttpUrl(value);
  if (!safe) return false;
  try {
    return new URL(safe).hostname.toLocaleLowerCase("es") === "opendata.gijon.es";
  } catch {
    return false;
  }
}

function isGijonOpenDataEvent(event, presentation) {
  const name = String(presentation?.sourceName || event?.source_name || "").toLocaleLowerCase("es");
  const source = safeHttpUrl(presentation?.sourceUrl || event?.source_url || event?.links?.source);
  return (name.includes("open data") && name.includes("gij")) || isGijonOpenDataUrl(source);
}

function gijonCorroboratingSource(event, presentation) {
  const candidates = [
    [event?.links?.municipal_page, "Ayuntamiento de Gijón/Xixón — ficha específica"],
    [presentation?.officialUrl, "Fuente oficial del evento"],
    [event?.links?.official, "Fuente oficial del evento"],
  ];
  for (const [value, label] of candidates) {
    const url = safeHttpUrl(value);
    if (url && !isGijonOpenDataUrl(url)) return { url, label };
  }
  return null;
}

function currentCityId() {
  const supported = new Set(["valparaiso", "gijon"]);
  const htmlCity = document.documentElement.dataset.city;
  if (supported.has(htmlCity)) return htmlCity;
  try {
    const saved = localStorage.getItem("agenda-cultural-city");
    if (supported.has(saved)) return saved;
  } catch {}
  return "valparaiso";
}

function permanentEventUrl(event) {
  const id = String(event?.id || "").trim();
  if (!id) return null;
  return new URL(`../evento/${currentCityId()}/${encodeURIComponent(id)}/`, window.location.href).href;
}

function calendarFileUrl(event) {
  const page = permanentEventUrl(event);
  return page ? new URL("evento.ics", page).href : null;
}

function hasCalendarDate(event) {
  return Boolean(event?.schedule?.start || event?.schedule?.occurrences?.[0]?.start);
}

function statusNotices(event) {
  const status = event?.public_status || {};
  const notices = [];
  if (status.cancelled === true) notices.push("Actividad cancelada");
  if (status.sold_out === true) notices.push("Entradas agotadas");
  if (status.registration_closed === true) notices.push("Inscripción cerrada");
  if (status.information_completeness && status.information_completeness !== "complete") {
    notices.push("Información pendiente de completar o confirmar");
  }
  if (status.advisory_text) notices.push(String(status.advisory_text));
  return [...new Set(notices)];
}

function buildMedia(event, presentation) {
  const resolved = resolveEventImage(event, {
    surface: "detail",
    baseUrl: window.location.href,
    allowDirect: presentation?.imageRelevant !== false,
  });
  const imageUrl = resolved.url;
  if (!imageUrl) return null;

  const media = document.createElement("div");
  media.className = "event-detail-media has-relevant-image";
  media.style.setProperty("--event-image", `url("${imageUrl.replaceAll('"', "%22")}")`);
  const image = document.createElement("img");
  image.src = imageUrl;
  image.dataset.eventImage = "relevant";
  image.alt = String(event?.image?.alt || event?.title || "Imagen de la actividad");
  image.decoding = "async";
  image.addEventListener("error", () => {
    const panel = media.closest(".event-detail-panel");
    media.remove();
    panel?.classList.add("event-detail-panel--no-media");
  }, { once: true });
  media.append(image);
  return media;
}

export function openEventDetail(event, presentation = {}) {
  document.querySelector("dialog[data-event-detail]")?.remove();

  const dialog = document.createElement("dialog");
  dialog.className = "event-detail-dialog";
  dialog.dataset.eventDetail = event?.id || "event";

  const panel = document.createElement("article");
  panel.className = "event-detail-panel";

  const close = document.createElement("button");
  close.type = "button";
  close.className = "event-detail-close";
  close.setAttribute("aria-label", "Cerrar ficha");
  close.textContent = "×";
  close.addEventListener("click", (eventClick) => {
    eventClick.preventDefault();
    dismissDialog(dialog);
  }, { capture: true });
  panel.append(close);

  const media = buildMedia(event, presentation);
  if (media) panel.append(media);
  else panel.classList.add("event-detail-panel--no-media");

  const content = document.createElement("div");
  content.className = "event-detail-content";

  const meta = document.createElement("div");
  meta.className = "event-detail-meta";
  addText(meta, "span", "event-detail-category", presentation.category || "Actividad cultural");
  if (presentation.type) addText(meta, "span", "event-detail-type", presentation.type);
  content.append(meta);

  const labels = Array.isArray(presentation.labels) ? [...new Set(presentation.labels)] : [];
  if (labels.length) {
    const badges = document.createElement("div");
    badges.className = "event-detail-badges";
    for (const label of labels) addText(badges, "span", "event-detail-badge", label);
    content.append(badges);
  }

  addText(content, "h2", "event-detail-title", event?.title || "Actividad sin título");

  const notices = statusNotices(event);
  if (notices.length) {
    const noticeBox = document.createElement("section");
    noticeBox.className = "event-detail-description event-detail-provenance";
    addText(noticeBox, "h3", "", "Avisos importantes");
    for (const notice of notices) addText(noticeBox, "p", "", notice);
    content.append(noticeBox);
  }

  const facts = document.createElement("div");
  facts.className = "event-detail-facts";
  addFact(facts, "Fecha y horario", presentation.schedule, "◷");
  addFact(facts, "Horario de visita", event?.schedule?.opening_hours?.display_text, "◷");
  addFact(facts, "Lugar", presentation.location, "⌖");
  addFact(facts, "Dirección", event?.location?.address, "↗");
  addFact(facts, "Precio", presentation.price, event?.price?.is_free === true ? "✓" : "$" );
  content.append(facts);

  const description = detailDescription(event);
  if (description) {
    const section = document.createElement("section");
    section.className = "event-detail-description";
    addText(section, "h3", "", "Sobre la actividad");
    addText(section, "p", "", description);
    content.append(section);
  }

  const gijonOpenData = isGijonOpenDataEvent(event, presentation);
  const corroborating = gijonOpenData ? gijonCorroboratingSource(event, presentation) : null;
  const extra = document.createElement("div");
  extra.className = "event-detail-extra";
  if (event?.organizer) addFact(extra, "Organiza", event.organizer, "•");
  if (event?.audience) addFact(extra, "Público", event.audience, "◎");
  if (gijonOpenData) {
    addFact(extra, "Fuente mostrada", corroborating?.label || "Open Data municipal (último recurso)", "✓");
  } else if (presentation.sourceName) {
    addFact(extra, "Fuente", presentation.sourceName, "✓");
  }
  if (extra.childElementCount) content.append(extra);

  if (gijonOpenData) {
    const provenance = document.createElement("section");
    provenance.className = "event-detail-description event-detail-provenance";
    addText(provenance, "h3", "", "Verificación de la información");
    addText(
      provenance,
      "p",
      "",
      corroborating
        ? "La actividad se detectó inicialmente mediante Open Data del Ayuntamiento de Gijón/Xixón, pero la fuente que se muestra al público es una ficha específica que corrobora la información del evento."
        : "La actividad se detectó mediante Open Data del Ayuntamiento de Gijón/Xixón. No se encontró todavía otra ficha específica verificable; Open Data se conserva únicamente como último recurso.",
    );
    content.append(provenance);
  }

  const actions = document.createElement("div");
  actions.className = "event-detail-actions";
  const tickets = safeHttpUrl(event?.links?.tickets);
  const registration = safeHttpUrl(event?.links?.registration || presentation.registrationUrl);
  const official = safeHttpUrl(presentation.officialUrl);
  const source = safeHttpUrl(presentation.sourceUrl);
  const permanent = permanentEventUrl(event);
  const calendar = calendarFileUrl(event);

  if (tickets) addExternalAction(actions, tickets, "Entradas ↗", "primary");
  else if (registration) addExternalAction(actions, registration, "Inscribirme ↗", "primary");

  if (calendar && hasCalendarDate(event)) {
    addExternalAction(actions, calendar, "Añadir al calendario", "secondary", { newTab: false });
  }

  if (permanent) {
    const shareButton = addButtonAction(actions, "Compartir", async () => {
      if (navigator.share) {
        try {
          await navigator.share({ title: event?.title || "Actividad cultural", url: permanent });
        } catch (error) {
          if (error?.name !== "AbortError") console.warn("No se pudo compartir el evento", error);
        }
        return;
      }
      const copied = await copyPermanentUrl(permanent);
      if (shareButton) {
        shareButton.textContent = copied ? "Enlace copiado ✓" : "No se pudo copiar";
        window.setTimeout(() => { shareButton.textContent = "Compartir"; }, 1800);
      }
    });
  }

  if (gijonOpenData) {
    if (corroborating) addExternalAction(actions, corroborating.url, "Fuente corroborante ↗");
    else if (source) addExternalAction(actions, source, "Open Data — último recurso ↗");
  } else if (official) {
    addExternalAction(actions, official, "Fuente oficial ↗");
  } else if (source) {
    addExternalAction(actions, source, "Fuente ↗");
  }

  if (actions.childElementCount) content.append(actions);

  panel.append(content);
  dialog.append(panel);
  document.body.append(dialog);

  dialog.addEventListener("click", (eventClick) => {
    if (eventClick.target === dialog) dismissDialog(dialog);
  });
  dialog.addEventListener("cancel", () => queueMicrotask(() => dialog.remove()), { once: true });
  dialog.addEventListener("close", () => dialog.remove(), { once: true });

  if (typeof dialog.showModal === "function") dialog.showModal();
  else dialog.setAttribute("open", "");
}
