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

function restoreAcronyms(value) {
  let text = value;
  for (const acronym of KNOWN_ACRONYMS) {
    text = text.replace(new RegExp(`\\b${acronym.toLocaleLowerCase("es")}\\b`, "giu"), acronym);
  }
  return text;
}

function upperFirst(value) {
  const chars = [...value];
  const index = chars.findIndex((char) => char.toLocaleLowerCase("es") !== char.toLocaleUpperCase("es"));
  if (index >= 0) chars[index] = chars[index].toLocaleUpperCase("es");
  return chars.join("");
}

function sentenceCase(value) {
  return upperFirst(restoreAcronyms(clean(value).toLocaleLowerCase("es")));
}

function smartTitleCase(value) {
  const originalWords = clean(value).split(/(\s+)/u);
  let wordIndex = 0;
  return originalWords.map((part) => {
    if (/^\s+$/u.test(part)) return part;
    const leading = part.match(/^[^\p{L}\p{N}]*/u)?.[0] || "";
    const trailing = part.match(/[^\p{L}\p{N}]*$/u)?.[0] || "";
    const end = trailing.length ? part.length - trailing.length : part.length;
    const core = part.slice(leading.length, end);
    const upperCore = core.toLocaleUpperCase("es");
    const lowerCore = core.toLocaleLowerCase("es");
    const firstWord = wordIndex++ === 0;
    if (KNOWN_ACRONYMS.has(upperCore)) return `${leading}${upperCore}${trailing}`;
    if (!firstWord && MINOR_WORDS.has(lowerCore)) return `${leading}${lowerCore}${trailing}`;
    return `${leading}${upperFirst(lowerCore)}${trailing}`;
  }).join("");
}

function smartAllCaps(value, event) {
  const category = String(event?.primary_category?.id || event?.categories?.[0]?.id || "").trim();
  if (category === "cursos-talleres") return sentenceCase(value);

  const sentences = clean(value).split(/(?<=[.!?])\s+/u);
  if (sentences.length > 1) {
    return sentences.map((sentence, index) => {
      const core = sentence.replace(/[.!?]+$/u, "");
      const punctuation = sentence.slice(core.length);
      const words = core.split(/\s+/u).filter(Boolean);
      const normalized = index === 0 && words.length <= 3 ? smartTitleCase(core) : sentenceCase(core);
      return `${normalized}${punctuation}`;
    }).join(" ");
  }

  const words = clean(value).split(/\s+/u).filter(Boolean);
  return words.length <= 3 ? smartTitleCase(value) : smartTitleCase(value);
}

export function normalizePublicEventTitle(value, event = null) {
  let text = normalizePublicTitle(value, event);
  text = stripTerminalPeriod(stripOuterQuotes(text));
  text = text.replace(GENERIC_PREFIX, "").trim();
  text = stripTerminalPeriod(stripOuterQuotes(text));
  if (isAllCaps(text)) text = smartAllCaps(text, event);
  return clean(text);
}
