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
      padding: .08rem 0 .34rem !important;
    }
    .discovery-heading,
    .filter-workbench-heading,
    .category-explorer-heading,
    .filter-help {
      display: none !important;
    }

    /* Keep only actionable controls in the filter surface. */
    .filter-workbench {
      gap: .48rem !important;
      padding: .58rem !important;
      border-radius: .9rem !important;
      box-shadow: none !important;
    }
    .filter-grid {
      gap: .48rem !important;
    }
    .filter-group {
      padding: .56rem .62rem !important;
      border-radius: .75rem !important;
    }
    .filter-group-title {
      margin-bottom: .34rem !important;
      font-size: .68rem !important;
      letter-spacing: .065em !important;
    }
    .filter-choice-row {
      gap: .3rem !important;
    }
    .filter-choice {
      padding: .39rem .54rem !important;
      gap: .3rem !important;
      font-size: .79rem !important;
      line-height: 1.05 !important;
    }
    .filter-choice small {
      min-width: 1.15rem !important;
      padding: .06rem .25rem !important;
      font-size: .65rem !important;
    }
    .custom-date-range {
      gap: .4rem !important;
      margin-top: .45rem !important;
    }
    .custom-date-range input {
      padding: .43rem .5rem !important;
    }
    .category-filter-panel {
      padding-top: 0 !important;
    }

    /* All quick filters stay visible. The grid grows vertically instead of
       hiding options behind a horizontal swipe. */
    .quick-sections {
      display: grid !important;
      grid-template-columns: repeat(auto-fit, minmax(128px, 1fr)) !important;
      gap: .42rem !important;
      padding: .12rem 0 .38rem !important;
      overflow: visible !important;
    }
    .quick-sections button {
      width: 100% !important;
      min-width: 0 !important;
      justify-content: center !important;
      padding: .5rem .62rem !important;
      gap: .38rem !important;
      font-size: .8rem !important;
      line-height: 1.05 !important;
    }
    .quick-sections button small {
      flex: 0 0 auto !important;
      min-width: 1.35rem !important;
      height: 1.35rem !important;
      padding: 0 .28rem !important;
      font-size: .68rem !important;
    }

    .category-explorer {
      margin-top: .12rem !important;
      padding: 0 !important;
      border: 0 !important;
      border-radius: 0 !important;
      background: transparent !important;
    }
    .category-filters {
      display: grid !important;
      grid-template-columns: repeat(auto-fit, minmax(138px, 1fr)) !important;
      gap: .32rem !important;
      overflow: visible !important;
      padding: 0 !important;
    }
    .category-chip {
      width: 100% !important;
      min-width: 0 !important;
      white-space: normal !important;
      justify-content: space-between !important;
      text-align: left !important;
      border-radius: .72rem !important;
      padding: .4rem .56rem !important;
      gap: .34rem !important;
      font-size: .78rem !important;
      line-height: 1.08 !important;
    }
    .category-chip span {
      min-width: 0 !important;
    }
    .category-chip small {
      flex: 0 0 auto !important;
      font-size: .64rem !important;
      min-width: 1.15rem !important;
      padding: .06rem .25rem !important;
    }

    .agenda {
      padding: .05rem 0 3rem !important;
    }
    .agenda-heading {
      display: none !important;
    }

    .content-section {
      padding: .72rem 0 1rem !important;
    }
    /* The dated agenda is already the primary content immediately below the
       filters. Repeating "Agenda fechada" plus a count adds no decision value. */
    .content-section[data-dated-section] {
      padding-top: .16rem !important;
      border-top: 0 !important;
    }
    .content-section[data-dated-section] > .section-heading {
      display: none !important;
    }
    .secondary-section {
      margin-top: .2rem !important;
    }
    .section-heading {
      align-items: center !important;
      margin-bottom: .52rem !important;
    }
    .section-heading .eyebrow,
    .section-heading p:not(.eyebrow) {
      display: none !important;
    }
    .section-heading h3 {
      font-size: 1.14rem !important;
      line-height: 1.12 !important;
    }
    .section-count {
      padding: .36rem .54rem !important;
      font-size: .74rem !important;
    }
    .event-grid,
    .compact-grid {
      gap: .72rem !important;
    }
    .sources-section {
      padding-top: .75rem !important;
      margin-top: .38rem !important;
    }
    footer {
      padding: .85rem !important;
      font-size: .76rem !important;
    }

    @media (max-width: 760px) {
      .quick-sections {
        grid-template-columns: repeat(auto-fit, minmax(112px, 1fr)) !important;
      }
      .category-filters {
        grid-template-columns: repeat(auto-fit, minmax(124px, 1fr)) !important;
      }
    }

    @media (max-width: 560px) {
      .app-header {
        gap: .5rem !important;
      }
      .brand img {
        width: 34px !important;
        height: 34px !important;
      }
      .header-actions {
        gap: .3rem !important;
      }
      .install-button,
      .city-switch {
        padding: .42rem .55rem !important;
        font-size: .76rem !important;
      }
      .hero {
        padding-top: .42rem !important;
      }
      .hero .search-row input {
        min-height: 2.55rem !important;
      }
      .discovery {
        padding-bottom: .28rem !important;
      }
      .filter-workbench {
        gap: .4rem !important;
        padding: .46rem !important;
        border-radius: .72rem !important;
      }
      .filter-grid {
        gap: .38rem !important;
      }
      .filter-group {
        padding: .48rem .52rem !important;
      }
      .filter-choice {
        padding: .36rem .48rem !important;
        font-size: .76rem !important;
      }
      .quick-sections,
      .category-filters {
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
      }
      .category-chip {
        border-radius: .68rem !important;
        padding: .38rem .5rem !important;
        font-size: .76rem !important;
      }
      .section-heading {
        gap: .4rem !important;
      }
    }
  `;
  document.head.append(style);
}
