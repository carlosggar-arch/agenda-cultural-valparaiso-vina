const DATASET_URL = "./agenda_web.json";

function validHttpUrl(value) {
  try {
    const url = new URL(String(value || ""), window.location.href);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch { return null; }
}

function categoryId(event) {
  return event?.primary_category?.id || event?.categories?.[0]?.id || "cultura";
}

function categoryLabel(event) {
  return event?.primary_category?.label || event?.categories?.[0]?.label || "Actividad cultural";
}

function fallbackArtwork(event) {
  const placeholder = document.createElement("div");
  placeholder.className = "placeholder";
  placeholder.dataset.theme = categoryId(event);
  placeholder.setAttribute("role", "img");
  placeholder.setAttribute("aria-label", `Ilustración de categoría: ${categoryLabel(event)}.`);
  const label = document.createElement("span");
  label.className = "placeholder-label";
  label.textContent = categoryLabel(event);
  placeholder.append(label);
  return placeholder;
}

function installImageFallback(card, event) {
  const image = card.querySelector(".card-media img");
  if (!image || image.dataset.fallbackBound === "true") return;
  image.dataset.fallbackBound = "true";
  image.addEventListener("error", () => {
    const media = image.closest(".card-media");
    if (!media) return;
    media.replaceChildren(fallbackArtwork(event));
  }, { once: true });
}

function visitHours(event) {
  const schedule = event?.schedule || {};
  const opening = String(schedule.opening_time || "").match(/^\d{2}:\d{2}$/)?.[0];
  const closing = String(schedule.closing_time || "").match(/^\d{2}:\d{2}$/)?.[0];
  return opening && closing ? `${opening}–${closing}` : null;
}

function dateOnly(value) {
  const text = String(value || "");
  if (!text) return null;
  const datePart = text.slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(datePart)) return null;
  const [year, month, day] = datePart.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day, 12));
  return new Intl.DateTimeFormat("es-CL", {
    timeZone: "UTC",
    weekday: "short",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(date);
}

function visitScheduleLabel(event) {
  const hours = visitHours(event);
  if (!hours) return null;
  const startDate = dateOnly(event?.schedule?.start);
  const endDate = dateOnly(event?.schedule?.end);
  if (startDate && endDate && String(event.schedule.start).slice(0, 10) !== String(event.schedule.end).slice(0, 10)) {
    return `${startDate} – ${endDate} · ${hours}`;
  }
  return `${startDate || "Horario de visita"} · ${hours}`;
}

function enhanceCard(card, event) {
  installImageFallback(card, event);
  const label = visitScheduleLabel(event);
  if (label) {
    const date = card.querySelector(".card-date");
    if (date) date.textContent = label;
  }
}

function enhanceDetail(event) {
  const label = visitScheduleLabel(event);
  if (!label) return;
  const dialog = document.querySelector("[data-detail-dialog]");
  if (!dialog?.open) return;
  const terms = [...dialog.querySelectorAll("dt")];
  const term = terms.find((node) => node.textContent.trim() === "Fecha y horario");
  if (term?.nextElementSibling) term.nextElementSibling.textContent = label;
}

async function start() {
  let payload;
  try {
    const response = await fetch(DATASET_URL, { headers: { Accept: "application/json" } });
    if (!response.ok) return;
    payload = await response.json();
  } catch { return; }
  const events = new Map((payload.events || []).map((event) => [String(event.id), event]));

  const apply = () => {
    document.querySelectorAll(".event-card[data-event-id]").forEach((card) => {
      const event = events.get(card.dataset.eventId);
      if (event) enhanceCard(card, event);
    });
    const requested = new URL(window.location.href).searchParams.get("evento");
    const event = events.get(String(requested || ""));
    if (event) enhanceDetail(event);
  };

  const observer = new MutationObserver(apply);
  observer.observe(document.body, { childList: true, subtree: true });
  apply();
}

start();
