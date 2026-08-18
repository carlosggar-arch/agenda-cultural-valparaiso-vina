import "./vivamos-brand.js";

const STORAGE_KEY = "agenda-cultural-city";
const CITIES = {
  valparaiso: {
    label: "Valparaíso / Viña del Mar",
    submittedCities: "Valparaíso,Viña del Mar",
    theme: "#174f46",
  },
  gijon: {
    label: "Gijón / Xixón",
    submittedCities: "Gijón",
    theme: "#0d5e73",
  },
};

function resolveCity() {
  const requested = new URLSearchParams(window.location.search).get("city");
  let saved = null;
  try { saved = localStorage.getItem(STORAGE_KEY); } catch {}
  return CITIES[requested] ? requested : CITIES[saved] ? saved : "valparaiso";
}

function classifyPrimarySource(rawUrl) {
  const value = String(rawUrl || "").trim();
  if (!value) return null;
  try {
    const host = new URL(value).hostname.toLowerCase().replace(/^www\./, "");
    if (host === "instagram.com" || host.endsWith(".instagram.com")) return ["instagram_url", value];
    if (host === "facebook.com" || host.endsWith(".facebook.com") || host === "fb.com") return ["facebook_url", value];
    return ["website_url", value];
  } catch {
    return null;
  }
}

const cityId = resolveCity();
const city = CITIES[cityId];
document.documentElement.dataset.city = cityId;
document.querySelector('meta[name="theme-color"]')?.setAttribute("content", city.theme);

const badge = document.querySelector("[data-city-badge]");
const cityInput = document.querySelector("[data-city-input]");
const subtitle = document.querySelector("[data-city-subtitle]");
if (badge) badge.textContent = `📍 ${city.label}`;
if (cityInput) cityInput.value = city.submittedCities;
if (subtitle) subtitle.textContent = city.label;

const form = document.querySelector("[data-community-source-form]");
const message = form?.querySelector("[data-form-message]");
let pendingIdempotencyKey = null;

form?.addEventListener("input", () => { pendingIdempotencyKey = null; });

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!form || !message) return;

  const apiBase = document.querySelector('meta[name="community-api-base"]')?.content?.replace(/\/$/, "");
  if (!apiBase) {
    message.textContent = "El formulario todavía no está habilitado.";
    return;
  }

  const values = Object.fromEntries(new FormData(form));
  values.cities = city.submittedCities;

  const primarySource = classifyPrimarySource(values.source_url);
  delete values.source_url;
  if (!primarySource) {
    message.textContent = "Indica un enlace público válido.";
    return;
  }
  const [primaryField, primaryUrl] = primarySource;
  if (!String(values[primaryField] || "").trim()) values[primaryField] = primaryUrl;

  const categories = form.querySelector('select[name="categories"]');
  const selectedCategories = categories ? [...categories.selectedOptions].map((option) => option.value) : [];
  values.categories = selectedCategories.length ? selectedCategories.join(",") : "Otros panoramas";

  values.contact_name = String(values.contact_name || "").trim() || "No indicado";
  for (const checkbox of form.querySelectorAll('input[type="checkbox"]')) values[checkbox.name] = checkbox.checked;
  values.turnstile_token = values["cf-turnstile-response"] || "";
  delete values["cf-turnstile-response"];

  const sourceUrls = [values.website_url, values.instagram_url, values.facebook_url, values.calendar_url, values.feed_url]
    .map((value) => String(value || "").trim())
    .filter(Boolean);
  if (!sourceUrls.length) {
    message.textContent = "Indica al menos una fuente pública.";
    return;
  }

  const button = form.querySelector('button[type="submit"]');
  pendingIdempotencyKey ||= crypto.randomUUID();
  if (button) button.disabled = true;
  message.textContent = "Enviando para revisión…";

  try {
    const response = await fetch(`${apiBase}/community/v1/submissions/organizations`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": pendingIdempotencyKey,
      },
      body: JSON.stringify(values),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "No fue posible recibir la propuesta.");

    message.textContent = `Fuente recibida. La revisaremos antes de incorporarla. Referencia: ${result.reference}`;
    pendingIdempotencyKey = null;
    form.reset();
    if (cityInput) cityInput.value = city.submittedCities;
    window.turnstile?.reset();
  } catch (error) {
    message.textContent = error instanceof Error ? error.message : "No fue posible conectar con el servicio.";
    window.turnstile?.reset();
  } finally {
    if (button) button.disabled = false;
  }
});
