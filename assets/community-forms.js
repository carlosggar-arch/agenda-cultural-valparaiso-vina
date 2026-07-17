const form = document.querySelector("[data-community-form]");
const message = form?.querySelector("[data-form-message]");
let pendingIdempotencyKey = null;

form?.addEventListener("input", () => {
  pendingIdempotencyKey = null;
});

const cityPolicyUrl = document.querySelector('meta[name="publication-cities-url"]')?.content;
if (form && cityPolicyUrl) {
  fetch(cityPolicyUrl)
    .then((response) => {
      if (!response.ok) throw new Error("No se pudo cargar la cobertura territorial.");
      return response.json();
    })
    .then((policy) => {
      for (const select of form.querySelectorAll("[data-publication-city-select]")) {
        if (!select.multiple) select.append(new Option("Selecciona una ciudad", ""));
        for (const city of policy.cities) select.append(new Option(city.name, city.name));
      }
    })
    .catch(() => { message.textContent = "No fue posible cargar las ciudades admitidas."; });
}

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const apiBase = document.querySelector('meta[name="community-api-base"]')?.content?.replace(/\/$/, "");
  if (!apiBase) { message.textContent = "El formulario todavía no está habilitado."; return; }
  const values = Object.fromEntries(new FormData(form));
  const cities = form.querySelector('select[name="cities"]');
  if (cities) values.cities = [...cities.selectedOptions].map((option) => option.value).join(",");
  for (const checkbox of form.querySelectorAll('input[type="checkbox"]')) values[checkbox.name] = checkbox.checked;
  values.turnstile_token = values["cf-turnstile-response"] || "";
  delete values["cf-turnstile-response"];
  const endpoint = form.dataset.communityForm === "event" ? "events" : "organizations";
  const button = form.querySelector('button[type="submit"]');
  pendingIdempotencyKey ||= crypto.randomUUID();
  button.disabled = true;
  message.textContent = "Enviando para revisión…";
  try {
    const response = await fetch(`${apiBase}/community/v1/submissions/${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Idempotency-Key": pendingIdempotencyKey },
      body: JSON.stringify(values),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "No fue posible recibir la propuesta.");
    message.textContent = `Solicitud recibida en pending_review. Referencia: ${result.reference}`;
    pendingIdempotencyKey = null;
    form.reset();
    window.turnstile?.reset();
  } catch (error) {
    message.textContent = error instanceof Error ? error.message : "No fue posible conectar con el servicio.";
    window.turnstile?.reset();
  } finally {
    button.disabled = false;
  }
});
