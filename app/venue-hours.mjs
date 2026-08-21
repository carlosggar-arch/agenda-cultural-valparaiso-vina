import { venueRecordForEvent } from "./venue-identity.mjs?v=20260821-venueidentity1";

function fold(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[’‘`]/g, "'")
    .toLocaleLowerCase("es")
    .replace(/[—−]/g, "–")
    .replace(/\s+/g, " ")
    .trim();
}

function venueKey(value) {
  return fold(value)
    .replace(/[^a-z0-9']+/g, " ")
    .replace(/^(?:museo|museu|museum)\s+/, "")
    .trim();
}

const VALPARAISO_VENUE_HOURS = new Map();

function registerValparaiso(names, display, source, verifiedAt = "2026-08-19") {
  const record = Object.freeze({ display, source, verified_at: verifiedAt });
  for (const name of names) VALPARAISO_VENUE_HOURS.set(venueKey(name), record);
}

registerValparaiso(
  ["Museo de Historia Natural de Valparaíso"],
  "Mar–vie 10:00–18:00 · sáb 11:00–16:00 · dom, lun y festivos cerrado.",
  "https://www.mhnv.gob.cl/planifica-tu-visita",
);
registerValparaiso(
  ["Museo Palacio Rioja", "Palacio Rioja"],
  "Mar–dom 10:00–17:30.",
  "https://visitavina.munivina.cl/museo-palacio-rioja/",
);
registerValparaiso(
  ["Museo Palacio Vergara", "Palacio Vergara"],
  "Mar–dom 10:00–17:30.",
  "https://visitavina.munivina.cl/museo-palacio-vergara/",
);
registerValparaiso(
  ["Museo Baburizza", "Palacio Baburizza"],
  "Mar–dom 10:00–18:00.",
  "https://www.museobaburizza.cl/visita/",
);
registerValparaiso(
  ["Museo Fonck"],
  "Lun 10:00–14:00 y 15:00–18:00 · mar–sáb 10:00–18:00 · dom y festivos 10:00–14:00.",
  "https://museofonck.cl/new_site/index.php/horario-y-valores",
);
registerValparaiso(
  ["Museo Artequin", "Museo Artequín", "Artequin Viña del Mar", "Artequín Viña del Mar"],
  "Mar–vie 09:00–17:00 · sáb–dom 10:00–18:00.",
  "https://visitavina.munivina.cl/museos-y-palacios/artequin-vina-del-mar/",
);
registerValparaiso(
  ["Museo Marítimo Nacional", "Museo Maritimo Nacional"],
  "Lun–dom 10:00–18:00 · último ingreso 17:30.",
  "https://museomaritimo.cl/horarios/",
);

const MONTHS = Object.freeze({
  ene: 1, enero: 1, feb: 2, febrero: 2, marzo: 3, abr: 4, abril: 4,
  may: 5, mayo: 5, jun: 6, junio: 6, jul: 7, julio: 7, ago: 8, agosto: 8,
  sep: 9, sept: 9, septiembre: 9, oct: 10, octubre: 10, nov: 11, noviembre: 11,
  dic: 12, diciembre: 12,
});
const WEEKDAYS = Object.freeze({
  lun: 0, lunes: 0, mar: 1, martes: 1, mie: 2, miercoles: 2,
  jue: 3, jueves: 3, vie: 4, viernes: 4, sab: 5, sabado: 5,
  dom: 6, domingo: 6,
});
const TIME_RANGE = /\b([0-2]\d:[0-5]\d)\s*[–-]\s*([0-2]\d:[0-5]\d)(?:\s+y\s+([0-2]\d:[0-5]\d)\s*[–-]\s*([0-2]\d:[0-5]\d))?/i;

function explicitHours(event) {
  const schedule = event?.schedule || {};
  const opening = schedule?.opening_hours || {};
  const candidates = [opening.display_text, schedule.venue_opening_hours, schedule.visit_hours, event?.location?.opening_hours];
  const display = candidates.map((item) => String(item || "").replace(/\s+/g, " ").trim()).find(Boolean);
  if (!display) return null;
  return {
    display,
    source: String(opening.source_url || schedule.venue_hours_source_url || "").trim() || null,
    source_name: String(opening.source_name || schedule.venue_hours_source_name || "").trim() || null,
    verified_at: String(opening.verified_at || schedule.venue_hours_verified_at || "").trim() || null,
  };
}

function registryHours(event, cityId) {
  const record = venueRecordForEvent(event);
  const opening = record?.opening_hours;
  if (opening?.display) {
    return {
      display: String(opening.display).trim(),
      source: opening.source_url || null,
      source_name: opening.source_name || null,
      verified_at: opening.verified_at || null,
    };
  }
  if (cityId === "valparaiso") {
    const name = String(event?.location?.venue || "").trim();
    return VALPARAISO_VENUE_HOURS.get(venueKey(name)) || null;
  }
  return null;
}

function consensusExplicitHours(events) {
  const records = events.map(explicitHours).filter(Boolean);
  if (!records.length) return null;
  const byDisplay = new Map();
  for (const record of records) {
    const list = byDisplay.get(record.display) || [];
    list.push(record);
    byDisplay.set(record.display, list);
  }
  if (byDisplay.size !== 1) return null;
  const [display, matches] = [...byDisplay.entries()][0];
  const enriched = matches.find((record) => record.source || record.verified_at) || matches[0];
  return { ...enriched, display };
}

function dateParts(dateKey) {
  const match = String(dateKey || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const weekday = (new Date(Date.UTC(year, month - 1, day, 12)).getUTCDay() + 6) % 7;
  return { year, month, day, weekday };
}

function monthNumber(token) {
  return MONTHS[fold(token).replace(/[^a-z]/g, "")] || null;
}

function inCyclicRange(value, start, end) {
  return start <= end ? start <= value && value <= end : value >= start || value <= end;
}

function monthQualifierMatches(text, parts, { allowShortMarch = false } = {}) {
  const value = fold(text);
  if (!value) return null;
  const dated = value.match(/\b(\d{1,2})\s+(ene(?:ro)?|feb(?:rero)?|marzo|abr(?:il)?|may(?:o)?|jun(?:io)?|jul(?:io)?|ago(?:sto)?|sep(?:t(?:iembre)?)?|oct(?:ubre)?|nov(?:iembre)?|dic(?:iembre)?)\s*[–-]\s*(\d{1,2})\s+(ene(?:ro)?|feb(?:rero)?|marzo|abr(?:il)?|may(?:o)?|jun(?:io)?|jul(?:io)?|ago(?:sto)?|sep(?:t(?:iembre)?)?|oct(?:ubre)?|nov(?:iembre)?|dic(?:iembre)?)/);
  if (dated) {
    const startMonth = monthNumber(dated[2]);
    const endMonth = monthNumber(dated[4]);
    const current = parts.month * 100 + parts.day;
    const start = startMonth * 100 + Number(dated[1]);
    const end = endMonth * 100 + Number(dated[3]);
    return start <= end ? start <= current && current <= end : current >= start || current <= end;
  }
  const monthToken = allowShortMarch
    ? "ene(?:ro)?|feb(?:rero)?|mar(?:zo)?|abr(?:il)?|may(?:o)?|jun(?:io)?|jul(?:io)?|ago(?:sto)?|sep(?:t(?:iembre)?)?|oct(?:ubre)?|nov(?:iembre)?|dic(?:iembre)?"
    : "ene(?:ro)?|feb(?:rero)?|marzo|abr(?:il)?|may(?:o)?|jun(?:io)?|jul(?:io)?|ago(?:sto)?|sep(?:t(?:iembre)?)?|oct(?:ubre)?|nov(?:iembre)?|dic(?:iembre)?";
  const range = value.match(new RegExp(`\\b(${monthToken})\\s*[–-]\\s*(${monthToken})\\b`));
  if (range) return inCyclicRange(parts.month, monthNumber(range[1]), monthNumber(range[2]));
  const tokens = [...value.matchAll(new RegExp(`\\b(${monthToken})\\b`, "g"))].map((match) => monthNumber(match[1])).filter(Boolean);
  return tokens.length ? tokens.includes(parts.month) : null;
}

function weekdayQualifierMatches(text, weekday) {
  const value = fold(text);
  const token = "lun(?:es)?|mar(?:tes)?|mie(?:rcoles)?|jue(?:ves)?|vie(?:rnes)?|sab(?:ado)?|dom(?:ingo)?";
  const range = value.match(new RegExp(`\\b(${token})\\s*[–-]\\s*(${token})\\b`));
  if (range) return inCyclicRange(weekday, WEEKDAYS[fold(range[1]).slice(0, 3)], WEEKDAYS[fold(range[2]).slice(0, 3)]);
  const matches = [...value.matchAll(new RegExp(`\\b(${token})\\b`, "g"))]
    .map((match) => WEEKDAYS[fold(match[1]).slice(0, 3)])
    .filter((item) => Number.isInteger(item));
  return matches.length ? matches.includes(weekday) : null;
}

function rangeLabel(text) {
  const match = String(text || "").match(TIME_RANGE);
  if (!match) return null;
  return match[3] && match[4] ? `${match[1]}–${match[2]} y ${match[3]}–${match[4]}` : `${match[1]}–${match[2]}`;
}

export function dateSpecificHours(display, dateKey) {
  const parts = dateParts(dateKey);
  if (!parts) return null;
  const whole = fold(display);
  if (!whole) return null;
  if (parts.weekday === 0) {
    if (/lunes cerrado/.test(whole)) return "Cerrado";
    if (/habitualmente mar[–-]dom/.test(whole) && !(/lunes tambien abre en julio y agosto/.test(whole) && [7, 8].includes(parts.month))) return "Cerrado";
  }

  const chunks = String(display || "")
    .replace(/\.\s+(?=[A-ZÁÉÍÓÚÑ0-9])/g, " · ")
    .split(/\s*·\s*/)
    .map((item) => item.trim())
    .filter(Boolean);
  let activeSeason = true;
  let sawApplicableTimedClause = false;
  let sawRejectedWeekdayClause = false;
  for (const chunk of chunks) {
    const time = rangeLabel(chunk);
    const explicitMonth = monthQualifierMatches(chunk, parts, { allowShortMarch: !time });
    if (!time && explicitMonth !== null) {
      activeSeason = explicitMonth;
      continue;
    }
    if (!time) continue;
    const monthMatch = monthQualifierMatches(chunk, parts, { allowShortMarch: false });
    const appliesSeason = monthMatch === null ? activeSeason : monthMatch;
    if (!appliesSeason) continue;
    sawApplicableTimedClause = true;
    const appliesWeekday = weekdayQualifierMatches(chunk, parts.weekday);
    if (appliesWeekday === false) {
      sawRejectedWeekdayClause = true;
      continue;
    }
    return time;
  }
  if (sawApplicableTimedClause && sawRejectedWeekdayClause) return "Cerrado";
  return null;
}

export function venueHoursForEvents(events, cityId) {
  const list = (events || []).filter(Boolean);
  if (!list.length) return null;
  const explicit = consensusExplicitHours(list);
  if (explicit) return explicit;
  for (const event of list) {
    const record = registryHours(event, cityId);
    if (record?.display) return record;
  }
  return null;
}

export function venueHoursForDate(event, cityId, referenceDateKey) {
  if (!event || !referenceDateKey) return null;
  const record = registryHours(event, cityId) || explicitHours(event);
  if (!record?.display) return null;
  const display = dateSpecificHours(record.display, referenceDateKey);
  if (!display) return null;
  return { ...record, display, reference_date: referenceDateKey };
}

export { VALPARAISO_VENUE_HOURS, venueKey };