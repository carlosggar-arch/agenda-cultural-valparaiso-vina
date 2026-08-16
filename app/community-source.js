const styleHref = new URL("./community-source.css", import.meta.url).href;
if (![...document.styleSheets].some((sheet) => sheet.href === styleHref)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = styleHref;
  document.head.append(link);
}

function activeCityId() {
  return document.documentElement.dataset.city === "gijon" ? "gijon" : "valparaiso";
}

function syncLink(link) {
  const url = new URL("./proponer-fuente.html", window.location.href);
  url.searchParams.set("city", activeCityId());
  link.href = `${url.pathname}${url.search}`;
}

function mountSourceProposal() {
  const section = document.querySelector("[data-sources-section]");
  const grid = section?.querySelector("[data-sources-grid]");
  if (!section || !grid || section.querySelector("[data-source-proposal-cta]")) return;

  const cta = document.createElement("aside");
  cta.className = "source-proposal-cta";
  cta.dataset.sourceProposalCta = "";
  cta.innerHTML = `
    <div>
      <strong>¿Conoces una fuente que debería estar aquí?</strong>
      <p>Propón una organización, espacio o canal. La revisaremos antes de incorporarla.</p>
    </div>
    <a class="source-proposal-link" data-source-proposal-link>+ Proponer una fuente</a>
  `;
  grid.insertAdjacentElement("afterend", cta);
  const link = cta.querySelector("[data-source-proposal-link]");
  if (link) syncLink(link);
}

mountSourceProposal();
new MutationObserver(() => {
  mountSourceProposal();
  const link = document.querySelector("[data-source-proposal-link]");
  if (link) syncLink(link);
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });
