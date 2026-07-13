export const DATASET_PATH = "./agenda_web.json";
export const SUPPORTED_SCHEMA_MAJOR = 1;
export const DISPLAY_TIME_ZONE = "America/Santiago";

export class AgendaDataError extends Error {
  constructor(message, code = "invalid") {
    super(message);
    this.name = "AgendaDataError";
    this.code = code;
  }
}

const REQUIRED_ENTRY_FIELDS = [
  "id",
  "title",
  "event_type",
  "categories",
  "schedule",
  "location",
  "price",
  "links",
];

export function validateDataset(data) {
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    throw new AgendaDataError("El archivo de agenda no contiene un objeto JSON válido.");
  }
  if (typeof data.schema_version !== "string") {
    throw new AgendaDataError("El dataset no declara una versión de esquema.", "incompatible");
  }
  const major = Number.parseInt(data.schema_version.split(".")[0], 10);
  if (major !== SUPPORTED_SCHEMA_MAJOR) {
    throw new AgendaDataError(
      `La versión ${data.schema_version} de la agenda no es compatible con esta página.`,
      "incompatible",
    );
  }
  if (!Array.isArray(data.events)) {
    throw new AgendaDataError("El dataset no contiene un arreglo de actividades.");
  }
  data.events.forEach((event, index) => {
    if (!event || typeof event !== "object" || Array.isArray(event)) {
      throw new AgendaDataError(`La actividad ${index + 1} no tiene una estructura válida.`);
    }
    const missing = REQUIRED_ENTRY_FIELDS.filter((field) => !(field in event));
    if (missing.length) {
      throw new AgendaDataError(
        `La actividad ${index + 1} no contiene: ${missing.join(", ")}.`,
      );
    }
  });
  return data;
}

export async function fetchDataset(fetchImplementation = globalThis.fetch, path = DATASET_PATH) {
  let response;
  try {
    response = await fetchImplementation(path, { headers: { Accept: "application/json" } });
  } catch (error) {
    throw new AgendaDataError(
      "No fue posible conectar con el archivo público de la agenda.",
      "load",
      { cause: error },
    );
  }
  if (!response || !response.ok) {
    throw new AgendaDataError(
      `No fue posible cargar la agenda${response ? ` (HTTP ${response.status})` : ""}.`,
      "load",
    );
  }
  let data;
  try {
    data = await response.json();
  } catch (error) {
    throw new AgendaDataError("El archivo de agenda no contiene JSON válido.", "load", { cause: error });
  }
  return validateDataset(data);
}

export function safeHttpUrl(value) {
  if (!value) return null;
  try {
    const parsed = new URL(String(value));
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.href : null;
  } catch {
    return null;
  }
}

export const EVENT_TYPE_LABELS = {
  event: "Evento",
  course: "Curso",
  workshop: "Taller",
  flexible_offer: "Horario flexible",
  program: "Cartelera o programa",
};

export function eventTypeLabel(value) {
  return EVENT_TYPE_LABELS[value] || "Actividad";
}

function dateFromContract(value) {
  if (!value) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return new Date(`${value}T12:00:00-04:00`);
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function formatContractDate(value, { includeTime = true } = {}) {
  const date = dateFromContract(value);
  if (!date) return null;
  const hasTime = includeTime && String(value).includes("T");
  return new Intl.DateTimeFormat("es-CL", {
    timeZone: DISPLAY_TIME_ZONE,
    weekday: "short",
    day: "numeric",
    month: "long",
    year: "numeric",
    ...(hasTime ? { hour: "2-digit", minute: "2-digit", hour12: false } : {}),
  }).format(date);
}

export function formatGeneratedAt(value) {
  const date = dateFromContract(value);
  if (!date) return "Fecha de actualización no disponible";
  return `Actualizada ${new Intl.DateTimeFormat("es-CL", {
    timeZone: DISPLAY_TIME_ZONE,
    dateStyle: "long",
    timeStyle: "short",
  }).format(date)}`;
}

export function scheduleLabel(schedule) {
  if (!schedule || typeof schedule !== "object") return null;
  if (schedule.start) {
    const formatted = formatContractDate(schedule.start);
    if (formatted) return formatted;
  }
  if (Array.isArray(schedule.occurrences) && schedule.occurrences.length) {
    const formatted = formatContractDate(schedule.occurrences[0]?.start);
    if (formatted) return formatted;
  }
  return schedule.display_text || null;
}

export function priceLabel(price) {
  if (!price || typeof price !== "object") return "Precio no informado";
  if (price.is_free === true) return "Gratis";
  if (price.is_free === false) return price.display_text || "Actividad pagada";
  return price.display_text || "Precio no informado";
}

export function findEventById(events, id) {
  if (!id || !Array.isArray(events)) return null;
  return events.find((event) => event.id === id) || null;
}

export const FILTER_PARAM_NAMES = [
  "q", "ciudad", "categoria", "precio", "periodo", "desde", "hasta", "gratis",
];

export const PRICE_FILTERS = new Set(["todos", "gratis", "pagado", "desconocido"]);
export const PERIOD_FILTERS = new Set(["todos", "hoy", "manana", "fin-de-semana", "rango"]);

export function normalizeSearchText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es-CL")
    .trim();
}

export function slugifyFilterValue(value) {
  return normalizeSearchText(value)
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

export function collectCategories(events) {
  const categories = new Map();
  (events || []).forEach((event) => {
    (event.categories || []).forEach((category) => {
      if (category?.id && category?.label && !categories.has(category.id)) {
        categories.set(category.id, category.label);
      }
    });
  });
  return [...categories].map(([id, label]) => ({ id, label }))
    .sort((a, b) => a.label.localeCompare(b.label, "es-CL"));
}

export function collectCities(events) {
  const cities = new Map();
  (events || []).forEach((event) => {
    const label = event.location?.city;
    const id = slugifyFilterValue(label);
    if (id && label && !cities.has(id)) cities.set(id, label);
  });
  return [...cities].map(([id, label]) => ({ id, label }))
    .sort((a, b) => a.label.localeCompare(b.label, "es-CL"));
}

export function defaultFilterState() {
  return {
    query: "",
    city: "",
    categories: [],
    price: "todos",
    period: "todos",
    from: "",
    to: "",
  };
}

export function filtersFromSearchParams(input) {
  const params = input instanceof URLSearchParams ? input : new URLSearchParams(input || "");
  const state = defaultFilterState();
  state.query = (params.get("q") || "").trim();
  state.city = slugifyFilterValue(params.get("ciudad") || "");
  state.categories = [...new Set((params.get("categoria") || "").split(",").map((value) => value.trim().toLocaleLowerCase("es-CL")).filter(Boolean))];
  const price = params.get("precio") || (params.get("gratis") === "true" ? "gratis" : "todos");
  state.price = PRICE_FILTERS.has(price) ? price : "todos";
  const period = params.get("periodo") || ((params.has("desde") || params.has("hasta")) ? "rango" : "todos");
  state.period = PERIOD_FILTERS.has(period) ? period : "todos";
  state.from = /^\d{4}-\d{2}-\d{2}$/.test(params.get("desde") || "") ? params.get("desde") : "";
  state.to = /^\d{4}-\d{2}-\d{2}$/.test(params.get("hasta") || "") ? params.get("hasta") : "";
  return state;
}

export function filtersToSearchParams(filters, input = "") {
  const params = input instanceof URLSearchParams ? new URLSearchParams(input) : new URLSearchParams(input);
  FILTER_PARAM_NAMES.forEach((name) => params.delete(name));
  if (filters.query) params.set("q", filters.query);
  if (filters.city) params.set("ciudad", filters.city);
  if (filters.categories?.length) params.set("categoria", filters.categories.join(","));
  if (filters.price && filters.price !== "todos") params.set("precio", filters.price);
  if (filters.period && filters.period !== "todos") params.set("periodo", filters.period);
  if (filters.period === "rango" && filters.from) params.set("desde", filters.from);
  if (filters.period === "rango" && filters.to) params.set("hasta", filters.to);
  return params;
}

export function clearFilterParams(input = "") {
  return filtersToSearchParams(defaultFilterState(), input);
}

function localParts(value) {
  const date = value instanceof Date ? value : dateFromContract(value);
  if (!date || Number.isNaN(date.getTime())) return null;
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: DISPLAY_TIME_ZONE,
    year: "numeric", month: "2-digit", day: "2-digit",
    weekday: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).formatToParts(date);
  const get = (type) => parts.find((part) => part.type === type)?.value;
  return {
    date: `${get("year")}-${get("month")}-${get("day")}`,
    weekday: get("weekday"),
    minutes: Number(get("hour")) * 60 + Number(get("minute")),
  };
}

function addUtcDays(dateText, days) {
  const date = new Date(`${dateText}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export function periodBounds(period, now = new Date(), from = "", to = "") {
  const localNow = localParts(now);
  if (!localNow) return null;
  if (period === "hoy") return { from: localNow.date, to: localNow.date };
  if (period === "manana") {
    const tomorrow = addUtcDays(localNow.date, 1);
    return { from: tomorrow, to: tomorrow };
  }
  if (period === "rango") return { from: from || null, to: to || null };
  if (period === "fin-de-semana") {
    const dayIndex = { Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6, Sun: 7 }[localNow.weekday];
    let daysToFriday = 5 - dayIndex;
    if (dayIndex === 7 && localNow.minutes > 23 * 60 + 59) daysToFriday += 7;
    const friday = addUtcDays(localNow.date, daysToFriday);
    return { from: friday, to: addUtcDays(friday, 2), fromMinutes: 18 * 60, toMinutes: 23 * 60 + 59 };
  }
  return null;
}

function eventStarts(event) {
  return [...new Set([
    event.schedule?.start,
    ...(event.schedule?.occurrences || []).map((occurrence) => occurrence?.start),
  ].filter(Boolean))];
}

function isWithinPeriod(event, filters, now) {
  if (filters.period === "todos") return true;
  const bounds = periodBounds(filters.period, now, filters.from, filters.to);
  if (!bounds) return true;
  return eventStarts(event).some((value) => {
    const start = localParts(value);
    if (!start) return false;
    if (bounds.from && start.date < bounds.from) return false;
    if (bounds.to && start.date > bounds.to) return false;
    if (filters.period === "fin-de-semana" && start.date === bounds.from && start.minutes < bounds.fromMinutes) return false;
    if (filters.period === "fin-de-semana" && start.date === bounds.to && start.minutes > bounds.toMinutes) return false;
    return true;
  });
}

function matchesPrice(event, price) {
  if (price === "todos") return true;
  if (price === "gratis") return event.price?.is_free === true;
  if (price === "pagado") return event.price?.is_free === false;
  return event.price?.is_free !== true && event.price?.is_free !== false;
}

export function filterEvents(events, filters = defaultFilterState(), now = new Date()) {
  const query = normalizeSearchText(filters.query);
  const selectedCategories = new Set(filters.categories || []);
  return (events || []).filter((event) => {
    const searchable = normalizeSearchText([
      event.title, event.description, event.organizer,
      event.location?.venue, event.location?.city,
      ...(event.categories || []).flatMap((category) => [category?.id, category?.label]),
    ].filter(Boolean).join(" "));
    if (query && !searchable.includes(query)) return false;
    if (filters.city && slugifyFilterValue(event.location?.city) !== filters.city) return false;
    if (selectedCategories.size && !(event.categories || []).some((category) => selectedCategories.has(category?.id))) return false;
    if (!matchesPrice(event, filters.price || "todos")) return false;
    return isWithinPeriod(event, filters, now);
  });
}
