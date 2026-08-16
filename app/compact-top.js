const STYLE_ID = "agenda-compact-top-style";

if (!document.getElementById(STYLE_ID)) {
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .app-header {
      padding-top: .62rem !important;
      padding-bottom: .62rem !important;
    }
    .brand img {
      width: 40px !important;
      height: 40px !important;
    }
    .brand strong {
      font-size: .94rem !important;
    }
    .brand small {
      font-size: .76rem !important;
    }
    .install-button,
    .city-switch {
      padding: .52rem .72rem !important;
      font-size: .82rem !important;
    }

    .hero {
      margin-top: 0 !important;
      padding: .68rem 0 .15rem !important;
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
      min-height: 2.8rem !important;
      padding: .68rem .9rem !important;
      border-radius: 999px !important;
      font-size: .9rem !important;
      box-shadow: 0 6px 18px color-mix(in srgb, var(--brand) 8%, transparent) !important;
    }

    .status {
      margin-top: .35rem !important;
      padding: .8rem 1rem !important;
    }

    .discovery {
      padding: .15rem 0 .55rem !important;
    }
    .discovery-heading,
    .category-explorer-heading {
      display: none !important;
    }
    .quick-sections {
      gap: .38rem !important;
      padding: .12rem 0 .34rem !important;
      scrollbar-width: none;
    }
    .quick-sections::-webkit-scrollbar,
    .category-filters::-webkit-scrollbar {
      display: none;
    }
    .quick-sections button {
      padding: .46rem .62rem !important;
      gap: .38rem !important;
      font-size: .8rem !important;
      line-height: 1 !important;
    }
    .quick-sections button small {
      min-width: 1.35rem !important;
      height: 1.35rem !important;
      padding: 0 .28rem !important;
      font-size: .68rem !important;
    }

    .category-explorer {
      margin-top: .08rem !important;
      padding: 0 !important;
      border: 0 !important;
      border-radius: 0 !important;
      background: transparent !important;
    }
    .category-filters {
      display: flex !important;
      flex-wrap: nowrap !important;
      gap: .38rem !important;
      overflow-x: auto !important;
      padding: .06rem 0 .28rem !important;
      scrollbar-width: none;
    }
    .category-chip {
      flex: 0 0 auto !important;
      white-space: nowrap !important;
      border-radius: 999px !important;
      padding: .43rem .58rem !important;
      gap: .36rem !important;
      font-size: .8rem !important;
    }
    .category-chip small {
      font-size: .66rem !important;
      min-width: 1.2rem !important;
      padding: .08rem .28rem !important;
    }

    .agenda {
      padding: .1rem 0 3rem !important;
    }
    .agenda-heading {
      display: none !important;
    }

    .content-section {
      padding: .8rem 0 1.15rem !important;
    }
    .secondary-section {
      margin-top: .25rem !important;
    }
    .section-heading {
      align-items: center !important;
      margin-bottom: .62rem !important;
    }
    .section-heading .eyebrow,
    .section-heading p:not(.eyebrow) {
      display: none !important;
    }
    .section-heading h3 {
      font-size: 1.18rem !important;
      line-height: 1.15 !important;
    }
    .section-count {
      padding: .4rem .6rem !important;
      font-size: .76rem !important;
    }
    .event-grid,
    .compact-grid {
      gap: .78rem !important;
    }
    .sources-section {
      padding-top: .85rem !important;
      margin-top: .45rem !important;
    }
    footer {
      padding: 1rem !important;
      font-size: .78rem !important;
    }

    @media (max-width: 560px) {
      .app-header {
        gap: .55rem !important;
      }
      .brand img {
        width: 36px !important;
        height: 36px !important;
      }
      .header-actions {
        gap: .35rem !important;
      }
      .install-button,
      .city-switch {
        padding: .46rem .6rem !important;
        font-size: .78rem !important;
      }
      .hero {
        padding-top: .5rem !important;
      }
      .hero .search-row input {
        min-height: 2.65rem !important;
      }
      .discovery {
        padding-bottom: .4rem !important;
      }
      .section-heading {
        gap: .45rem !important;
      }
    }
  `;
  document.head.append(style);
}
