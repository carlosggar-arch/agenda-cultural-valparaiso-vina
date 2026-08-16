const BRAND_NAME = "¡Vivamos!";

function applyVivamosBrand() {
  document.documentElement.dataset.brand = "vivamos";

  if (document.title.includes("Agenda Cultural")) {
    document.title = document.title.replace("Agenda Cultural", BRAND_NAME);
  } else if (document.title === "Agenda Cultural") {
    document.title = BRAND_NAME;
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

  const chooserBrand = document.querySelector("[data-chooser] > .eyebrow");
  if (chooserBrand) chooserBrand.textContent = BRAND_NAME;
}

applyVivamosBrand();

export { BRAND_NAME, applyVivamosBrand };
