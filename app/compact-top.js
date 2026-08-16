const STYLE_ID = "agenda-compact-top-style";

if (!document.getElementById(STYLE_ID)) {
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .hero {
      margin-top: 0 !important;
      padding: 1rem 0 .35rem !important;
      border: 0 !important;
      border-radius: 0 !important;
      background: transparent !important;
      box-shadow: none !important;
      overflow: visible !important;
    }
    .hero::before,
    .hero::after,
    .hero > .eyebrow,
    .hero > h1,
    .hero > .hero-copy {
      display: none !important;
    }
    .hero .search-row {
      margin-top: 0 !important;
    }
    .hero .search-row label {
      display: block;
      width: 100%;
    }
    .hero .search-row input {
      width: 100% !important;
      max-width: none !important;
      min-height: 3.25rem;
      padding: .82rem 1rem !important;
      border-radius: 999px !important;
      box-shadow: 0 8px 24px color-mix(in srgb, var(--brand) 9%, transparent) !important;
    }
    .discovery {
      padding-top: .45rem !important;
    }
    .status {
      margin-top: .45rem !important;
    }
    @media (max-width: 560px) {
      .hero {
        padding-top: .7rem !important;
      }
      .hero .search-row input {
        min-height: 3rem;
      }
    }
  `;
  document.head.append(style);
}
