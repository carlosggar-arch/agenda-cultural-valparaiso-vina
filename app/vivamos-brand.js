const BRAND_NAME = "¡Vivamos!";
const BRAND_TAGLINE = "Descubre y vive lo que hay cerca de ti.";

function applyVivamosBrand() {
  document.documentElement.dataset.brand = "vivamos";

  if (document.title.includes("Agenda Cultural")) {
    document.title = document.title.replace("Agenda Cultural", BRAND_NAME);
  }

  const description = document.querySelector('meta[name="description"]');
  if (description?.content.includes("Agenda Cultural")) {
    description.content = description.content.replace("Agenda Cultural", BRAND_NAME);
  }

  document.querySelectorAll(".brand strong").forEach((node) => {
    node.textContent = BRAND_NAME;
  });

  document.querySelectorAll(".brand[aria-label]").forEach((node) => {
    const label = node.getAttribute("aria-label") || "";
    node.setAttribute("aria-label", label.replace("Agenda Cultural", BRAND_NAME));
  });

  const footerBrand = document.querySelector("footer > strong");
  if (footerBrand) footerBrand.textContent = BRAND_NAME;

  const footerTagline = document.querySelector("footer > span");
  if (footerTagline) footerTagline.textContent = BRAND_TAGLINE;

  const chooserBrand = document.querySelector("[data-chooser] > .eyebrow");
  if (chooserBrand) chooserBrand.textContent = BRAND_NAME;
}

applyVivamosBrand();

const titleNode = document.querySelector("title");
if (titleNode) {
  new MutationObserver(() => {
    if (document.title.includes("Agenda Cultural")) applyVivamosBrand();
  }).observe(titleNode, { childList: true, subtree: true });
}

new MutationObserver(applyVivamosBrand).observe(document.documentElement, {
  attributes: true,
  attributeFilter: ["data-city"],
});

export { BRAND_NAME, BRAND_TAGLINE, applyVivamosBrand };
