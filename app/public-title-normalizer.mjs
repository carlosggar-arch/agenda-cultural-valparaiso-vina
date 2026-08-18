import { normalizePublicTitle } from "./public-presentation-rules.mjs?v=20260818-presentation4";

const KNOWN_ACRONYMS = new Set([
  "AI", "DJ", "DJS", "FMCE", "IA", "LGBT", "LGBTQ", "MNHN", "ONU", "PUCV",
  "SCD", "SIDA", "UAI", "UNESCO", "UP", "USM", "UTFSM", "UV", "VIH",
]);
const MINOR_WORDS = new Set(["a", "al", "de", "del", "el", "en", "la", "las", "los", "o", "para", "por", "y"]);
const GENERIC_PREFIX = /^(?:actividad|obra(?:\s+de\s+teatro)?|concierto|recital|exposici[oó]n(?:\s+temporal)?|exhibici[oó]n|muestra|charla|taller|curso|funci[oó]n)\s*(?:(?:\/\/|[:|–—-])\s*|(?=["“‘'«‹]))/iu;
const OUTER_QUOTES = [["\"", "\""], ["“", "”"], ["‘", "’"], ["'", "'"], ["«", "»"], ["‹", "›"]];

function clean(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function stripOuterQuotes(value) {
  let text = clean(value);
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
  const text = clean(value);
  return text.endsWith(".") && !text.endsWith("...") ? text.slice(0, -1).trim() : text;
}

function isAllCaps(value) {
  const letters = [...String(value || "")].filter((char) => char.toLocaleLowerCase("es") !== char.toLocaleUpperCase("es"));
  return letters.length >= 5 && letters.every((char) => char === char.toLocaleUpperCase("es"));
}

function smartTitleCase(value) {
  const originalWords = clean(value).split(/(\s+)/u);
  let wordIndex = 0;
  return originalWords.map((part) => {
    if (/^\s+$/u.test(part)) return part;
    const leading = part.match(/^[^\p{L}\p{N}]*/u)?.[0] || "";
    const trailing = part.match(/[^\p{L}\p{N}]*$/u)?.[0] || "";
    const core = part.slice(leading.length, part.length - trailing.length || undefined);
    const upperCore = core.toLocaleUpperCase("es");
    const lowerCore = core.toLocaleLowerCase("es");
    const firstWord = wordIndex++ === 0;
    if (KNOWN_ACRONYMS.has(upperCore)) return `${leading}${upperCore}${trailing}`;
    if (!firstWord && MINOR_WORDS.has(lowerCore)) return `${leading}${lowerCore}${trailing}`;
    const chars = [...lowerCore];
    const letter = chars.findIndex((char) => char.toLocaleLowerCase("es") !== char.toLocaleUpperCase("es"));
    if (letter >= 0) chars[letter] = chars[letter].toLocaleUpperCase("es");
    return `${leading}${chars.join("")}${trailing}`;
  }).join("");
}

export function normalizePublicEventTitle(value, event = null) {
  let text = normalizePublicTitle(value, event);
  text = stripTerminalPeriod(stripOuterQuotes(text));
  text = text.replace(GENERIC_PREFIX, "").trim();
  text = stripTerminalPeriod(stripOuterQuotes(text));
  if (isAllCaps(text)) text = smartTitleCase(text);
  return clean(text);
}
