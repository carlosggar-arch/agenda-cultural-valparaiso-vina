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

function detailDescription(event) {
  const text = String(event?.description || "")
    .replace(/<[^>]+>/g, " ")
    .replace(/\\n/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!text || /^actividad publicada en la agenda/i.test(text)) return null;
  return text;
}

function isGijonOpenDataEvent(event, presentation) {
  const name = String(presentation?.sourceName || event?.source_name || "").toLocaleLowerCase("es");
  const source = safeHttpUrl(presentation?.sourceUrl || event?.source_url || event?.links?.source);
  return (name.includes("open data") && name.includes("gij"))
    || Boolean(source?.startsWith("https://opendata.gijon.es/"));
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
  const media = document.createElement("div");
  media.className = "event-detail-media";
  const imageUrl = presentation?.imageRelevant === false ? null : safeHttpUrl(event?.image?.url);
  if (imageUrl) {
    media.classList.add("has-relevant-image");
    media.style.setProperty("--event-image", `url("${imageUrl.replaceAll('"', "%22")}")`);
    const image = document.createElement("img");
    image.src = imageUrl;
    image.dataset.eventImage = "relevant";
    image.alt = String(event?.image?.alt || event?.title || "Imagen de la actividad");
    image.decoding = "async";
    image.addEventListener("error", () => {
      media.classList.remove("has-relevant-image");
      media.style.removeProperty("--event-image");
      media.replaceChildren();
      const fallback = document.createElement("div");
      fallback.className = "event-media-fallback";
      addText(fallback, "span", "event-media-fallback-symbol", "✦")?.setAttribute("aria-hidden", "true");
      addText(fallback, "span", "event-media-fallback-label", presentation?.category || "Actividad cultural");
      media.append(fallback);
    }, { once: true });
    media.append(image);
    return media;
  }

  const fallback = document.createElement("div");
  fallback.className = "event-media-fallback";
  addText(fallback, "span", "event-media-fallback-symbol", "✦")?.setAttribute("aria-hidden", "true");
  addText(
    fallback,
    "span",
    "event-media-fallback-label",
    presentation?.imageRelevant === false ? "Sin imagen específica del evento" : presentation?.category || "Actividad cultural",
  );
  media.append(fallback);
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
  close.addEventListener("click", () => dialog.close());
  panel.append(close);

  panel.append(buildMedia(event, presentation));

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
  const extra = document.createElement("div");
  extra.className = "event-detail-extra";
  if (event?.organizer) addFact(extra, "Organiza", event.organizer, "•");
  if (event?.audience) addFact(extra, "Público", event.audience, "◎");
  if (presentation.sourceName) addFact(extra, gijonOpenData ? "Datos oficiales" : "Fuente", presentation.sourceName, "✓");
  if (extra.childElementCount) content.append(extra);

  if (gijonOpenData) {
    const provenance = document.createElement("section");
    provenance.className = "event-detail-description event-detail-provenance";
    addText(provenance, "h3", "", "Información oficial disponible");
    addText(
      provenance,
      "p",
      "",
      "Esta ficha reproduce los datos oficiales publicados por Open Data del Ayuntamiento de Gijón/Xixón. Para evitar páginas municipales individuales que no muestran contenido, la Agenda ofrece directamente la inscripción cuando está disponible y conserva Open Data como referencia oficial.",
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
  if (registration && registration !== tickets) addExternalAction(actions, registration, "Inscribirme ↗", "primary");
  if (calendar && hasCalendarDate(event)) addExternalAction(actions, calendar, "Añadir al calendario", "secondary", { newTab: false });
  if (permanent) addExternalAction(actions, permanent, "Ficha permanente →", "secondary", { newTab: false });

  if (permanent) {
    addButtonAction(actions, "Compartir", async () => {
      if (navigator.share) {
        try {
          await navigator.share({ title: event?.title || "Actividad cultural", url: permanent });
        } catch (error) {
          if (error?.name !== "AbortError") console.warn("No se pudo compartir el evento", error);
        }
        return;
      }
      try { await navigator.clipboard.writeText(permanent); } catch {}
    });
    addButtonAction(actions, "Copiar enlace", async () => {
      try { await navigator.clipboard.writeText(permanent); } catch {}
    });
  }

  if (gijonOpenData) {
    if (source && source !== registration && source !== tickets) addExternalAction(actions, source, "Open Data oficial ↗");
  } else {
    if (official && official !== registration && official !== tickets) addExternalAction(actions, official, "Fuente oficial ↗");
    if (source && source !== official && source !== registration && source !== tickets) addExternalAction(actions, source, "Fuente de datos ↗");
  }
  if (actions.childElementCount) content.append(actions);

  panel.append(content);
  dialog.append(panel);
  document.body.append(dialog);

  dialog.addEventListener("click", (eventClick) => {
    if (eventClick.target === dialog) dialog.close();
  });
  dialog.addEventListener("close", () => dialog.remove(), { once: true });

  if (typeof dialog.showModal === "function") dialog.showModal();
  else dialog.setAttribute("open", "");
}
