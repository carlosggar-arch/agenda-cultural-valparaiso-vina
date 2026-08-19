const STYLE_ID = "multievent-layout-fix-styles";

if (!document.getElementById(STYLE_ID)) {
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .exhibition-group-list {
      max-height: 320px !important;
      overflow-y: auto !important;
      overflow-x: hidden !important;
    }

    .grouped-exhibition-item {
      height: auto !important;
      min-height: 74px !important;
      max-height: none !important;
      overflow: visible !important;
      align-items: center !important;
      padding-top: 8px !important;
      padding-bottom: 8px !important;
    }

    .grouped-exhibition-copy {
      min-width: 0 !important;
      overflow: visible !important;
    }

    .grouped-exhibition-copy strong {
      display: block !important;
      overflow: visible !important;
      -webkit-line-clamp: unset !important;
      -webkit-box-orient: initial !important;
      white-space: normal !important;
      overflow-wrap: anywhere !important;
      line-height: 1.18 !important;
    }

    .grouped-exhibition-copy small,
    .grouped-exhibition-price {
      display: block !important;
      overflow: visible !important;
      white-space: normal !important;
      text-overflow: clip !important;
      overflow-wrap: anywhere !important;
    }

    .grouped-exhibition-actions {
      align-self: center !important;
    }

    @media (max-width: 560px) {
      .exhibition-group-list { max-height: 300px !important; }
      .grouped-exhibition-item { min-height: 76px !important; }
    }
  `;
  document.head.append(style);
}
