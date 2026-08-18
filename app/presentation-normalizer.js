const STYLE_ID = "agenda-presentation-normalizer";

const KNOWN_ACRONYMS = Object.freeze([
  "AI", "DJ", "DJS", "IA", "LGBT", "LGBTQ", "MNHN", "ONU", "PUCV",
  "SIDA", "UAI", "UNESCO", "USM", "UTFSM", "UV", "VIH",
]);

const OUTER_QUOTES = Object.freeze([
  ['"', '"'],
  ['“', '”'],
  ['‘', '’'],
  ["'", "'"],
  ['«', '»'],
  ['‹', '›'],
]);

function installStyles() {
  let style = document.getElementById(STYLE_ID);
  if (!style) {
    style = document.createElement("style");
    style.id = STYLE_ID;
    document.head.append(style);
  }
  style.textContent = `
    /* One category component for normal and grouped cards. */
    .event-grid .exhibition-venue-body {
      display: flex !important;
      flex-direction: column !important;
      gap: .56rem !important;
      padding: .84rem .92rem .92rem !important;
    }

    .event-grid .exhibition-venue-meta {
      box-sizing: border-box !important;
      display: flex !important;
      align-items: flex-start !important;
      min-height: 1.6rem !important;
      margin: 0 !important;
      padding: 0 !important;
      font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
      font-size: .78rem !important;
      font-weight: 800 !important;
      line-height: normal !important;
      letter-spacing: .08em !important;
      text-transform: uppercase !important;
      color: #8d5a3b !important;
    }

    html[data-city="valparaiso"] .event-grid .exhibition-venue-meta,
    html[data-city="valparaiso"] .event-card .meta {
      color: #a9562f !important;
    }

    .event-grid .exhibition-venue-heading {
      margin: 0 !important;
    }

    .event-grid .exhibition-venue-facts {
      margin-top: 0 !important;
    }

    /* Keep category baselines identical even when a normal card has badges on the right. */
    .event-grid .event-card-body > .card-meta-row,
    .event-grid .exhibition-venue-meta {
      min-height: 1.6rem !important;
    }

    @media (max-width: 560px) {
      .event-grid .exhibition-venue-body {
        gap: .52rem !important;
        padding: .78rem .84rem .84rem !important;
      }
    }
  `;
}

function stripOuterQuotes(value) {
  let text = value.trim();
  let changed = true;
  while (changed && text.length > 1) {
    changed = false;
    for (const [open, close] of OUTER_QUOTES) {
      if (text.startsWith(open) && text.endsWith(close)) {
        text = text.slice(open.length, -close.length).trim();
        changed = true;
        break;
      }
    }
  }
  return text;
}

function stripTerminalPeriod(value) {
  const text = value.trim();
  if (text.endsWith(".") && !text.endsWith("...")) return text.slice(0, -1).trim();
  return text;
}

function isAllCapsTitle(value) {
  const letters = [...value].filter((char) => char.toLocaleLowerCase("es") !== char.toLocaleUpperCase("es"));
  return letters.length >= 5 && letters.every((char) => char === char.toLocaleUpperCase("es"));
}

function restoreKnownAcronyms(value) {
  let text = value;
  for (const acronym of KNOWN_ACRONYMS) {
    const escaped = acronym.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    text = text.replace(new RegExp(`\\b${escaped.toLocaleLowerCase("es")}\\b`, "giu"), acronym);
  }
  return text;
}

function sentenceCase(value) {
  let text = value.toLocaleLowerCase("es");
  text = restoreKnownAcronyms(text);
  const index = [...text].findIndex((char) => char.toLocaleLowerCase("es") !== char.toLocaleUpperCase("es"));
  if (index < 0) return text;

  const chars = [...text];
  chars[index] = chars[index].toLocaleUpperCase("es");
  return chars.join("");
}

export function normalizeDisplayTitle(value) {
  let text = String(value || "").replace(/\s+/g, " ").trim();
  if (!text) return text;

  // Titles such as “Foo.” or "Foo". are normalized regardless of punctuation order.
  for (let index = 0; index < 2; index += 1) {
    text = stripTerminalPeriod(text);
    text = stripOuterQuotes(text);
  }

  if (isAllCapsTitle(text)) text = sentenceCase(text);
  return text.trim();
}

function normalizeNode(node) {
  if (!(node instanceof HTMLElement)) return;
  const original = node.dataset.originalPublicTitle || node.textContent || "";
  if (!node.dataset.originalPublicTitle) node.dataset.originalPublicTitle = original;
  const normalized = normalizeDisplayTitle(original);
  if (normalized && node.textContent !== normalized) node.textContent = normalized;
}

function normalizeVisibleTitles(root = document) {
  const selectors = [
    '.event-card[data-event-id] .event-card-body h4',
    '.event-card[data-event-id]:not(.exhibition-venue-card) > h4',
    '.grouped-exhibition-copy strong',
  ];
  for (const node of root.querySelectorAll(selectors.join(','))) normalizeNode(node);
}

let queued = false;
function queueNormalize() {
  if (queued) return;
  queued = true;
  requestAnimationFrame(() => {
    queued = false;
    normalizeVisibleTitles();
  });
}

installStyles();
queueNormalize();

new MutationObserver(queueNormalize).observe(document.body, {
  childList: true,
  subtree: true,
  characterData: true,
});
