const REMINDER_OPTIONS = Object.freeze({
  "2h": Object.freeze({ id: "2h", label: "2 horas antes", trigger: "-PT2H", milliseconds: 2 * 60 * 60 * 1000 }),
  "1d": Object.freeze({ id: "1d", label: "1 día antes", trigger: "-P1D", milliseconds: 24 * 60 * 60 * 1000 }),
});

function text(value) {
  return String(value ?? "").trim();
}

function scheduleValue(event, field) {
  return event?.schedule?.[field] || event?.schedule?.occurrences?.[0]?.[field] || null;
}

function isDateOnly(value) {
  return /^\d{4}-\d{2}-\d{2}$/.test(text(value));
}

function parseDate(value, dateOnlyHour = 12) {
  const raw = text(value);
  if (!raw) return null;
  const date = new Date(isDateOnly(raw) ? `${raw}T${String(dateOnlyHour).padStart(2, "0")}:00:00` : raw);
  return Number.isNaN(date.getTime()) ? null : date;
}

function utcStamp(date) {
  return date.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}

function compactDate(value) {
  return text(value).replaceAll("-", "");
}

function addOneDay(value) {
  const [year, month, day] = text(value).split("-").map(Number);
  if (![year, month, day].every(Number.isFinite)) return null;
  const date = new Date(Date.UTC(year, month - 1, day + 1));
  return `${date.getUTCFullYear()}${String(date.getUTCMonth() + 1).padStart(2, "0")}${String(date.getUTCDate()).padStart(2, "0")}`;
}

function escapeIcs(value) {
  return text(value)
    .replaceAll("\\", "\\\\")
    .replaceAll("\r\n", "\\n")
    .replaceAll("\n", "\\n")
    .replaceAll(";", "\\;")
    .replaceAll(",", "\\,");
}

function safeHttpUrl(value) {
  const candidate = text(value);
  return /^https?:\/\//i.test(candidate) ? candidate : null;
}

function locationText(event) {
  const location = event?.location || {};
  const parts = [location.venue, location.address, location.city].map(text).filter(Boolean);
  return parts.filter((value, index) => parts.indexOf(value) === index).join(" · ");
}

function uidFor(city, event) {
  const cityPart = text(city).replace(/[^a-z0-9_-]+/gi, "-") || "agenda";
  const eventPart = text(event?.id).replace(/[^a-z0-9_-]+/gi, "-") || `event-${Date.now()}`;
  return `${cityPart}-${eventPart}@vivamos.local`;
}

export function reminderOptionsForEvent(event, now = new Date()) {
  const startRaw = scheduleValue(event, "start");
  const start = parseDate(startRaw);
  if (!start || Number.isNaN(now?.getTime?.()) || start <= now) return [];
  const remaining = start.getTime() - now.getTime();
  if (isDateOnly(startRaw)) {
    return remaining > REMINDER_OPTIONS["1d"].milliseconds ? [REMINDER_OPTIONS["1d"]] : [];
  }
  return [REMINDER_OPTIONS["2h"], REMINDER_OPTIONS["1d"]]
    .filter((option) => remaining > option.milliseconds);
}

export function buildReminderIcs({ city, event, pageUrl = null, lead = "1d", now = new Date() } = {}) {
  const option = REMINDER_OPTIONS[lead];
  const title = text(event?.title);
  const startRaw = scheduleValue(event, "start");
  if (!option || !title || !startRaw) return null;

  const start = parseDate(startRaw);
  if (!start) return null;
  const endRaw = scheduleValue(event, "end");
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Vivamos//Mis planes//ES",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "BEGIN:VEVENT",
    `UID:${escapeIcs(uidFor(city, event))}`,
    `DTSTAMP:${utcStamp(now)}`,
  ];

  if (isDateOnly(startRaw)) {
    const endDate = isDateOnly(endRaw) ? compactDate(endRaw) : addOneDay(startRaw);
    if (!endDate) return null;
    lines.push(`DTSTART;VALUE=DATE:${compactDate(startRaw)}`);
    lines.push(`DTEND;VALUE=DATE:${endDate}`);
  } else {
    let end = parseDate(endRaw);
    if (!end || end <= start) end = new Date(start.getTime() + 60 * 60 * 1000);
    lines.push(`DTSTART:${utcStamp(start)}`);
    lines.push(`DTEND:${utcStamp(end)}`);
  }

  lines.push(`SUMMARY:${escapeIcs(title)}`);
  const location = locationText(event);
  if (location) lines.push(`LOCATION:${escapeIcs(location)}`);
  const safePage = safeHttpUrl(pageUrl);
  if (safePage) lines.push(`URL:${safePage}`);
  lines.push(
    "BEGIN:VALARM",
    `TRIGGER:${option.trigger}`,
    "ACTION:DISPLAY",
    `DESCRIPTION:${escapeIcs(`Recordatorio: ${title}`)}`,
    "END:VALARM",
    "END:VEVENT",
    "END:VCALENDAR",
  );
  return `${lines.join("\r\n")}\r\n`;
}

export function reminderFilename(event) {
  const slug = text(event?.title)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 56) || "actividad";
  return `recordatorio-${slug}.ics`;
}

export function downloadReminderIcs(options = {}) {
  const ics = buildReminderIcs(options);
  if (!ics || typeof document === "undefined" || typeof URL === "undefined" || typeof Blob === "undefined") return false;
  const blob = new Blob([ics], { type: "text/calendar;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = reminderFilename(options.event);
  link.rel = "noopener";
  link.style.display = "none";
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1500);
  return true;
}
