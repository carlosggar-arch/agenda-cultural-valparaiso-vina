from pathlib import Path

ROOT = Path('.')


def replace_once(path, old, new, label):
    text = path.read_text(encoding='utf-8')
    if text.count(old) != 1:
        raise SystemExit(f'{label}: expected one marker, found {text.count(old)}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')

# 1) Runtime title recovery: malformed caption fragments must be recoverable,
# not only titles that equal the venue name. Preserve a semantic series prefix
# immediately before a quoted work title (e.g. Cápsula Radio: “La tercera luz”).
p = ROOT / 'app/title-normalizer-bootstrap.js'
replace_once(
    p,
    'const ACTIVITY_TERMS = /\\b(?:exposici[oó]n|muestra|obra|concierto|recital|festival|taller|charla|conversatorio|funci[oó]n|espect[aá]culo|presentaci[oó]n|encuentro|visita guiada|seminario|curso)\\b/iu;\nconst EXHIBITION_TERMS = /\\b(?:exposici[oó]n|muestra)\\b/iu;\n',
    'const ACTIVITY_TERMS = /\\b(?:instalaci[oó]n|exposici[oó]n|muestra|obra|concierto|recital|festival|taller|charla|conversatorio|funci[oó]n|espect[aá]culo|presentaci[oó]n|encuentro|visita guiada|seminario|curso)\\b/iu;\nconst EXHIBITION_TERMS = /\\b(?:instalaci[oó]n|exposici[oó]n|muestra)\\b/iu;\n',
    'activity terms',
)
replace_once(
    p,
    'function titleIsVenue(event) {\n',
    '''function titleLooksLikeCaptionFragment(event) {\n  const raw = String(event?.title || "").trim();\n  if (!raw) return false;\n  if (raw.length >= 72 && /[,;:]|\\b(?:cuyo|cuya|se descubre|visitando|hoy|agenda)\\b/iu.test(raw)) return true;\n  if (/^(?:\\d{1,2}[:.]\\d{2}\\s*h?|\\d{1,2}\\s+y\\s+las\\s+\\d{1,2}[:.]\\d{2})\\b/iu.test(raw)) return true;\n  return false;\n}\n\nfunction semanticPrefixBeforeQuote(description, start) {\n  const before = String(description || "").slice(Math.max(0, start - 70), start);\n  const match = before.match(/([\\p{L}][\\p{L}\\p{N} .+&/-]{2,42})\\s*:\\s*$/u);\n  if (!match) return "";\n  const prefix = cleanCandidate(match[1]);\n  const words = fold(prefix).split(/\\s+/).filter(Boolean);\n  if (!words.length || words.length > 6) return "";\n  if (/^(?:hoy|agenda|fuente|descripci[oó]n|informaci[oó]n)$/iu.test(prefix)) return "";\n  return prefix;\n}\n\nfunction titleIsVenue(event) {\n''',
    'caption helper insertion',
)
replace_once(
    p,
    'export function recoverExplicitActivityTitle(event) {\n  if (!titleIsVenue(event)) return null;\n',
    'export function recoverExplicitActivityTitle(event) {\n  if (!(titleIsVenue(event) || titleLooksLikeCaptionFragment(event))) return null;\n',
    'recovery eligibility',
)
replace_once(
    p,
    '      if (score >= 5) candidates.push({ candidate, score, start });\n',
    '''      if (score >= 5) {\n        const prefix = semanticPrefixBeforeQuote(description, start);\n        candidates.push({ candidate: prefix ? `${prefix}: ${candidate}` : candidate, score: prefix ? score + 1 : score, start });\n      }\n''',
    'prefixed quoted candidate',
)

# 2) Venue identity: ignore structural room/building qualifiers and use stable
# venue IDs when available. This allows "Primera planta del Antiguo Instituto
# Jovellanos" and "Centro de Cultura Antiguo Instituto" to reconcile without
# hard-coding either event title.
p = ROOT / 'app/event-identity-core.mjs'
replace_once(
    p,
    'const VENUE_STOPWORDS = new Set(["de", "del", "la", "el", "los", "las", "y", "e", "ex"]);\n',
    'const VENUE_STOPWORDS = new Set(["de", "del", "la", "el", "los", "las", "y", "e", "ex", "centro", "cultura", "primera", "planta"]);\n',
    'venue structural stopwords',
)
replace_once(
    p,
    'export function venuesLikelySame(a, b) {\n  const cityA = cityKey(a);\n',
    '''export function venuesLikelySame(a, b) {\n  const venueIdA = foldEventIdentity(a?.location?.venue_id);\n  const venueIdB = foldEventIdentity(b?.location?.venue_id);\n  if (venueIdA && venueIdB && venueIdA === venueIdB) return true;\n  const cityA = cityKey(a);\n''',
    'venue id authority',
)

# 3) Permanent title regression.
p = ROOT / 'app/title-normalizer-bootstrap.test.mjs'
replace_once(
    p,
    'import { normalizeAgendaTitles } from "./title-normalizer-bootstrap.js";\n',
    'import { normalizeAgendaTitles, recoverAgendaTitles } from "./title-normalizer-bootstrap.js";\n',
    'title test import',
)
replace_once(
    p,
    'console.log("TITLE_NORMALIZER_BOOTSTRAP_POINT7_OK");\n',
    '''const gijonRecovered = recoverAgendaTitles({\n  city: "gijon",\n  events: [{\n    id: "agenda-gijon-caption-fragment",\n    title: "00 y las 07:30h, La Sala emite el relato sonoro, cuyo desenlace se descubre visitando la instalación",\n    description: "Cápsula Radio: “La tercera luz”, de Alberto Conejero. Instalación de ficción sonora. Proyecto de Coma14 + Société Mouffette.",\n    source_id: "agenda_gijon",\n    source_name: "Agenda Gijón",\n    location: { venue: "Primera planta del Antiguo Instituto Jovellanos", city: "Gijón" },\n  }],\n});\nassert.equal(gijonRecovered.events[0].title, "Cápsula Radio: La tercera luz");\nassert.equal(gijonRecovered.events[0].editorial.title_original.startsWith("00 y las 07:30h"), true);\nassert.equal(gijonRecovered.events[0].editorial.category_recovery_hint, "exposiciones");\n\nconsole.log("TITLE_NORMALIZER_BOOTSTRAP_POINT7_OK");\n''',
    'title regression',
)

# 4) Permanent cross-source regression for generic official-vs-social authority.
p = ROOT / 'app/cross-source-deduplication.test.mjs'
append = r'''

test("Gijon recovered social caption reconciles with official installation record", () => {
  const social = event({
    id: "gijon-social-capsula",
    title: "Cápsula Radio: La tercera luz",
    sourceId: "agenda_gijon",
    sourceName: "Agenda Gijón",
    start: "2026-08-03T00:00:00+02:00",
    venue: "Primera planta del Antiguo Instituto Jovellanos",
    city: "Gijón",
  });
  social.primary_category = { id: "teatro", label: "Teatro y danza" };
  social.categories = [{ id: "teatro", label: "Teatro y danza" }];
  social.description = "Cápsula Radio: La tercera luz. Instalación de ficción sonora, radiocápsula y teatro de objetos.";
  social.public_status.source_official = false;
  social.source_url = "https://www.instagram.com/p/agenda-gijon-capsula/";
  social.links = { source: social.source_url };

  const official = event({
    id: "gijon-official-capsula",
    title: 'Instalación. Ficción sonora. CÁPSULA RADIO: "La tercera Luz"',
    sourceId: "gijon_opendata_events",
    sourceName: "Ayuntamiento de Gijón — Agenda",
    official: true,
    start: "2026-08-03T00:00:00+02:00",
    venue: "Centro de Cultura Antiguo Instituto",
    city: "Gijón",
  });
  official.primary_category = { id: "exposiciones", label: "Exposiciones" };
  official.categories = [{ id: "exposiciones", label: "Exposiciones" }];
  official.semantics = { source_category: { id: "exposiciones", label: "Exposiciones" }, primary_domain: "exposiciones", confidence: "high", score: 120 };
  official.source_url = "https://www.gijon.es/es/eventos/instalacion-ficcion-sonora-capsula-radio-la-tercera-luz";
  official.links = { official: official.source_url, source: official.source_url };

  assert.equal(venuesLikelySame(social, official), true, "building-floor wording must not split one venue");
  assert.equal(areProbableDuplicateEvents(social, official), true, "recovered work identity plus venue/date must reconcile");
  const result = deduplicateCrossSourceDataset({ counts: { total: 2, events: 2 }, events: [social, official] });
  assert.equal(result.events.length, 1);
  assert.equal(result.events[0].id, "gijon-official-capsula", "official municipal record must be canonical");
  assert.equal(result.events[0].primary_category.id, "exposiciones");
  assert.match(result.events[0].title, /CÁPSULA RADIO/i);
});
'''
text = p.read_text(encoding='utf-8')
if 'Gijon recovered social caption reconciles with official installation record' not in text:
    # Import venuesLikelySame through compatibility export.
    text = text.replace('  deduplicateCrossSourceDataset,\n', '  deduplicateCrossSourceDataset,\n  venuesLikelySame,\n', 1)
    text += append
    p.write_text(text, encoding='utf-8')

print('GIJON_CAPSULA_STRUCTURAL_PATCH_APPLIED')
