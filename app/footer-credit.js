const footer = document.querySelector("body > footer");

const PROFILE_URL = "https://github.com/carlosggar-arch";
const REPO_URL = "https://github.com/carlosggar-arch/agenda-cultural-valparaiso-vina";

if (footer) {
  footer.classList.add("vivamos-footer");
  footer.replaceChildren();

  const identity = document.createElement("div");
  identity.className = "vivamos-footer-identity";
  identity.innerHTML = "<strong>¡Vivamos!</strong><span>Agenda cultural independiente</span>";

  const credit = document.createElement("p");
  credit.className = "vivamos-footer-credit";
  credit.append("Creado y mantenido por ");
  const author = document.createElement("a");
  author.className = "vivamos-footer-author";
  author.href = PROFILE_URL;
  author.target = "_blank";
  author.rel = "noopener noreferrer";
  author.textContent = "Carlos García García";
  author.setAttribute("aria-label", "Carlos García García en GitHub");
  credit.append(author);

  const nav = document.createElement("nav");
  nav.className = "vivamos-footer-links";
  nav.setAttribute("aria-label", "Información y contacto");

  const links = [
    ["Contacto · @carlosggar-arch", PROFILE_URL, "contact"],
    ["GitHub", REPO_URL, "secondary"],
    ["Fuentes", "#sources-title", "secondary"],
  ];
  for (const [label, href, kind] of links) {
    const link = document.createElement("a");
    link.textContent = label;
    link.href = href;
    link.className = `vivamos-footer-link vivamos-footer-link--${kind}`;
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
      border-top: 1px solid rgba(255,255,255,.16);
      color: rgba(255,255,255,.82);
      font-size: .84rem;
    }
    .vivamos-footer-identity {
      display: flex;
      align-items: baseline;
      gap: .45rem;
      white-space: nowrap;
    }
    .vivamos-footer-identity strong {
      color: #fff !important;
    }
    .vivamos-footer-credit {
      margin: 0;
      min-width: 0;
      color: rgba(255,255,255,.82);
    }
    .vivamos-footer-author {
      color: #fff !important;
      font-weight: 800;
      text-decoration: underline;
      text-decoration-color: rgba(255,255,255,.55);
      text-underline-offset: 3px;
    }
    .vivamos-footer-author:hover,
    .vivamos-footer-author:focus-visible {
      text-decoration-color: #fff;
    }
    .vivamos-footer-links {
      display: flex;
      align-items: center;
      gap: .5rem;
      white-space: nowrap;
    }
    .vivamos-footer-link {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 2.25rem;
      padding: .48rem .68rem;
      border-radius: 999px;
      font-weight: 800;
      text-decoration: none !important;
      transition: background .15s ease, border-color .15s ease, color .15s ease;
    }
    .vivamos-footer-link--contact {
      color: #103c36 !important;
      background: #f4d16d;
      border: 1px solid #f4d16d;
    }
    .vivamos-footer-link--secondary {
      color: #fff !important;
      background: rgba(255,255,255,.08);
      border: 1px solid rgba(255,255,255,.34);
    }
    .vivamos-footer-link:hover,
    .vivamos-footer-link:focus-visible {
      background: #fff;
      border-color: #fff;
      color: #103c36 !important;
      outline: 2px solid rgba(255,255,255,.72);
      outline-offset: 2px;
    }
    .vivamos-footer [data-app-version] {
      white-space: nowrap;
      color: rgba(255,255,255,.76) !important;
    }
    @media (max-width: 900px) {
      .vivamos-footer {
        grid-template-columns: 1fr auto;
        align-items: start;
        gap: .6rem .8rem;
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
    @media (max-width: 560px) {
      .vivamos-footer {
        width: calc(100% - 1.4rem);
      }
      .vivamos-footer-identity {
        align-items: flex-start;
        flex-direction: column;
        gap: .15rem;
        white-space: normal;
      }
      .vivamos-footer-link {
        min-height: 2.15rem;
        padding: .44rem .62rem;
      }
    }
  `;
  document.head.append(style);
}
