const STYLE_ID = "multievent-layout-fix-styles";

if (!document.getElementById(STYLE_ID)) {
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .exhibition-group-list {
      max-height: 336px !important;
      overflow-y: auto !important;
      overflow-x: hidden !important;
      padding-bottom: 8px !important;
      scroll-padding-block: 8px !important;
    }

    .grouped-exhibition-item {
      box-sizing: border-box !important;
      height: auto !important;
      min-height: 92px !important;
      max-height: none !important;
      overflow: visible !important;
      align-items: center !important;
      padding-top: 10px !important;
      padding-bottom: 12px !important;
    }

    .grouped-exhibition-copy {
      min-width: 0 !important;
      overflow: visible !important;
      padding-block: 1px !important;
    }

    .grouped-exhibition-copy > * {
      max-width: 100% !important;
      overflow: visible !important;
      white-space: normal !important;
      text-overflow: clip !important;
      overflow-wrap: anywhere !important;
    }

    .grouped-exhibition-copy strong {
      display: block !important;
      margin-bottom: 4px !important;
      -webkit-line-clamp: unset !important;
      -webkit-box-orient: initial !important;
      line-height: 1.22 !important;
    }

    .grouped-exhibition-copy small {
      display: block !important;
      line-height: 1.25 !important;
    }

    .grouped-exhibition-price {
      display: block !important;
      margin-top: 3px !important;
      padding-bottom: 2px !important;
      line-height: 1.25 !important;
    }

    .grouped-exhibition-actions {
      align-self: center !important;
    }

    .exhibition-venue-hours {
      display: block !important;
      overflow: visible !important;
      white-space: normal !important;
      line-height: 1.28 !important;
    }

    @media (max-width: 560px) {
      .exhibition-group-list {
        max-height: 326px !important;
        padding-bottom: 10px !important;
      }

      .grouped-exhibition-item {
        min-height: 94px !important;
        padding-top: 10px !important;
        padding-bottom: 13px !important;
      }
    }
  `;
  document.head.append(style);
}
