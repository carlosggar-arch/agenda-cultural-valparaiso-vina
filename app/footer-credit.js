const footer = document.querySelector("body > footer");

if (footer) {
  footer.classList.add("vivamos-footer");
  footer.replaceChildren();

  const identity = document.createElement("div");
  identity.className = "vivamos-footer-identity";
  identity.innerHTML = "<strong>¡Vivamos!</strong><span>Agenda cultural independiente</span>";

  const credit = document.createElement("p");
  credit.className = "vivamos-footer-credit";
  credit.append("Creado y mantenido por ");
  const author = document.createElement("strong");
  author.textContent = "Carlos García García";
  credit.append(author);

  const nav = document.createElement("nav");
  nav.className = "vivamos-footer-links";
  nav.setAttribute("aria-label", "Información y contacto");

  const links = [
    ["Contacto", "https://github.com/carlosggar-arch"],
    ["GitHub", "https://github.com/carlosggar-arch/agenda-cultural-valparaiso-vina"],
    ["Fuentes", "#sources-title"],
  ];
  for (const [label, href] of links) {
    const link = document.createElement("a");
    link.textContent = label;
    link.href = href;
    if (href.startsWith("http")) {
      link.target = "_blank";
      link.rel = "noopener noreferrer";
    }
    nav.append(link);
  }

  const version = document.createElement("small");
  version.dataset.appVersion = "";
  version.textContent = "PWA";

  footer.append(identity, credit, nav, version);
}

const STYLE_ID = "vivamos-footer-credit-style";
if (!document.getElementById(STYLE_ID)) {
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .vivamos-footer {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr) auto auto;
      align-items: center;
      gap: .7rem 1.15rem;
      width: min(1120px, calc(100% - 2rem));
      margin: 0 auto;
      padding: 1.35rem 0 1.7rem;
      border-top: 1px solid var(--line, #dce5e2);
      color: #687b76;
      font-size: .84rem;
    }
    .vivamos-footer-identity {
      display: flex;
      align-items: baseline;
      gap: .45rem;
      white-space: nowrap;
    }
    .vivamos-footer-identity strong,
    .vivamos-footer-credit strong {
      color: var(--brand, #174f46);
    }
    .vivamos-footer-credit {
      margin: 0;
      min-width: 0;
    }
    .vivamos-footer-links {
      display: flex;
      align-items: center;
      gap: .75rem;
      white-space: nowrap;
    }
    .vivamos-footer-links a {
      color: var(--brand, #174f46);
      font-weight: 750;
      text-decoration: none;
    }
    .vivamos-footer-links a:hover,
    .vivamos-footer-links a:focus-visible {
      text-decoration: underline;
      text-underline-offset: 3px;
    }
    .vivamos-footer [data-app-version] {
      white-space: nowrap;
      color: #7b8b86;
    }
    @media (max-width: 760px) {
      .vivamos-footer {
        grid-template-columns: 1fr auto;
        align-items: start;
        gap: .55rem .8rem;
      }
      .vivamos-footer-identity,
      .vivamos-footer-credit,
      .vivamos-footer-links {
        grid-column: 1;
      }
      .vivamos-footer [data-app-version] {
        grid-column: 2;
        grid-row: 1;
      }
      .vivamos-footer-links {
        flex-wrap: wrap;
        white-space: normal;
      }
    }
  `;
  document.head.append(style);
}
