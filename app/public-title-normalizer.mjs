import { normalizePublicTitle } from "./public-presentation-rules.mjs?v=20260818-presentation4";

const KNOWN_ACRONYMS = new Set([
  "AI", "CMI", "DJ", "DJS", "FETEN", "FICX", "FMCE", "IA", "LGBT", "LGBTQ", "MNHN", "ONU", "PUCV",
  "SCD", "SIDA", "UAI", "UNESCO", "UP", "USM", "UTFSM", "UV", "VIH",
]);
const MINOR_WORDS = new Set(["a", "al", "de", "del", "el", "en", "la", "las", "los", "o", "para", "por", "y"]);
const GENERIC_PREFIX = /^(?:actividad|evento|teatro|obra(?:\s+de\s+teatro)?|concierto|recital|exposici[oó]n(?:\s+temporal)?|exhibici[oó]n|muestra|charla|taller|curso|funci[oó]n|cine|proyecci[oó]n|danza|m[uú]sica|espect[aá]culo|presentaci[oó]n|visita\s+guiada)\s*(?:(?:\/\/|[:|–—-])\s*|(?=["“‘'«‹]))/iu;
const OUTER_QUOTES = [["\"", "\""], ["“", "”"], ["‘", "’"], ["'", "'"], ["«", "»"], ["‹", "›"]];
const OPEN_QUOTE_CHARS = new Set(OUTER_QUOTES.map(([open]) => open));
const CLOSE_QUOTE_CHARS = new Set(OUTER_QUOTES.map(([, close]) => close));
const ROMAN_NUMERAL = /^(?=[IVXLCDM]+$)M{0,4}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})$/u;

function clean(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function escapeRegExp(value) {
  return String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function flexibleLiteral(value) {
  return escapeRegExp(clean(value)).replace(/\\\s+/g, "\\s+");
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
    if (changed || text.length <= 1) continue;
    const chars = [...text];
    if (OPEN_QUOTE_CHARS.has(chars[0]) && CLOSE_QUOTE_CHARS.has(chars.at(-1))) {
      text = chars.slice(1, -1).join("").trim();
      changed = true;
    }
  }
  return text;
}

function stripTerminalPeriod(value) {
  const text = clean(value);
  return text.endsWith(".") && !text.endsWith("...") ? text.slice(0, -1).trim() : text;
}

function stripKnownLocationSuffix(value, event) {
  let text = clean(value);
  const venue = clean(event?.location?.venue);
  const city = clean(event?.location?.city);
  if (!venue) return text;
  const venueRx = flexibleLiteral(venue);
  const cityRx = city ? flexibleLiteral(city) : null;
  const citySuffix = cityRx ? `(?:\\s*[,·|/–—-]\\s*|\\s+)${cityRx}` : "";
  const patterns = [
    new RegExp(`\\s+(?:en|@)\\s+${venueRx}${citySuffix}\\s*$`, "iu"),
    new RegExp(`\\s+(?:en|@)\\s+${venueRx}\\s*$`, "iu"),
  ];
  for (const pattern of patterns) {
    const candidate = text.replace(pattern, "").trim();
    if (candidate && candidate !== text) return candidate;
  }
  return text;
}

function casedLetters(value) {
  return [...String(value || "")].filter((char) => char.toLocaleLowerCase("es") !== char.toLocaleUpperCase("es"));
}

function isAllCaps(value) {
  const letters = casedLetters(value);
  return letters.length >= 5 && letters.every((char) => char === char.toLocaleUpperCase("es"));
}

function isMostlyAllCaps(value) {
  const letters = casedLetters(value);
  if (letters.length < 7) return false;
  const upper = letters.filter((char) => char === char.toLocaleUpperCase("es")).length;
  return upper / letters.length >= 0.8;
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

function protectedUpperToken(value) {
  const upper = String(value || "").toLocaleUpperCase("es");
  return KNOWN_ACRONYMS.has(upper) || ROMAN_NUMERAL.test(upper);
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
    if (protectedUpperToken(upperCore)) return `${leading}${upperCore}${trailing}`;
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
  return smartTitleCase(value);
}

function normalizeInternalAllCaps(value) {
  const parts = clean(value).split(/(\s*(?::|;|\/\/|—|–)\s*|\s+-\s+)/u);
  return parts.map((part, index) => {
    if (index % 2 === 1 || !isAllCaps(part)) return part;
    const words = clean(part).replace(/[.!?]+$/u, "").split(/\s+/u).filter(Boolean);
    const hasMinorWord = words.slice(1).some((word) => MINOR_WORDS.has(word.toLocaleLowerCase("es").replace(/[^\p{L}\p{N}]/gu, "")));
    return words.length <= 2 && !hasMinorWord ? smartTitleCase(part) : sentenceCase(part);
  }).join("");
}

function normalizeLeadingAllCapsRun(value) {
  const text = clean(value);
  const words = text.split(/\s+/u);
  if (words.length < 3) return text;

  let runLength = 0;
  let hasNormalizableWord = false;
  for (const word of words) {
    const leading = word.match(/^[^\p{L}\p{N}]*/u)?.[0] || "";
    const trailing = word.match(/[^\p{L}\p{N}]*$/u)?.[0] || "";
    const end = trailing.length ? word.length - trailing.length : word.length;
    const core = word.slice(leading.length, end);
    const letters = casedLetters(core);
    if (letters.length < 2 || !letters.every((char) => char === char.toLocaleUpperCase("es"))) break;
    runLength += 1;
    if (!protectedUpperToken(core)) hasNormalizableWord = true;
  }

  if (runLength < 2 || runLength >= words.length || !hasNormalizableWord) return text;
  const prefix = smartTitleCase(words.slice(0, runLength).join(" "));
  return clean(`${prefix} ${words.slice(runLength).join(" ")}`);
}

function stripGenericPrefixes(value) {
  let text = clean(value);
  for (let pass = 0; pass < 3; pass += 1) {
    const candidate = text.replace(GENERIC_PREFIX, "").trim();
    if (!candidate || candidate === text) break;
    text = stripTerminalPeriod(stripOuterQuotes(candidate));
  }
  return text;
}

export function normalizePublicEventTitle(value, event = null) {
  let text = normalizePublicTitle(value, event);
  text = stripKnownLocationSuffix(text, event);
  text = stripTerminalPeriod(stripOuterQuotes(text));
  text = stripGenericPrefixes(text);
  text = stripTerminalPeriod(stripOuterQuotes(text));
  if (isAllCaps(text) || isMostlyAllCaps(text)) text = smartAllCaps(text, event);
  else {
    text = normalizeInternalAllCaps(text);
    text = normalizeLeadingAllCapsRun(text);
  }
  return clean(text);
}
