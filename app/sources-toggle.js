const sourcesSection = document.querySelector("[data-sources-section]");
const footer = document.querySelector("footer");

if (sourcesSection && footer) {
  sourcesSection.id = "agenda-sources";

  const style = document.createElement("style");
  style.textContent = `
    [data-sources-section]:not(.sources-user-open){display:none!important}
    .sources-toggle{border:1px solid color-mix(in srgb,var(--brand) 24%,#fff);background:#fff;color:var(--brand);border-radius:999px;padding:.5rem .8rem;font-weight:800;cursor:pointer}
    .sources-toggle:hover,.sources-toggle:focus-visible{border-color:var(--accent)}
  `;
  document.head.append(style);

  const button = document.createElement("button");
  button.type = "button";
  button.className = "sources-toggle";
  button.dataset.sourcesToggle = "";
  button.setAttribute("aria-controls", "agenda-sources");
  button.setAttribute("aria-expanded", "false");
  button.textContent = "Fuentes";
  footer.append(button);

  button.addEventListener("click", () => {
    const opening = !sourcesSection.classList.contains("sources-user-open");
    sourcesSection.classList.toggle("sources-user-open", opening);
    button.setAttribute("aria-expanded", opening ? "true" : "false");
    button.textContent = opening ? "Ocultar fuentes" : "Fuentes";
    if (opening) sourcesSection.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}
