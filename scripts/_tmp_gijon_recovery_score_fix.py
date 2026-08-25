from pathlib import Path

p = Path('app/title-normalizer-bootstrap.js')
text = p.read_text(encoding='utf-8')
old = '''      if (ACTIVITY_TERMS.test(around)) score += 2;\n      if (/(?:exposici[oó]n|muestra|obra|concierto|recital|festival|taller|charla)\\s*(?:titulada?|llamada?)?\\s*$/iu.test(before)) score += 4;\n      if (start <= 12) score += 1;\n      if (words.length <= 10) score += 1;\n      if (score >= 5) {\n        const prefix = semanticPrefixBeforeQuote(description, start);\n        candidates.push({ candidate: prefix ? `${prefix}: ${candidate}` : candidate, score: prefix ? score + 1 : score, start });\n      }\n'''
new = '''      const hasActivityEvidence = ACTIVITY_TERMS.test(around);\n      if (hasActivityEvidence) score += 2;\n      if (/(?:instalaci[oó]n|exposici[oó]n|muestra|obra|concierto|recital|festival|taller|charla)\\s*(?:titulada?|llamada?)?\\s*$/iu.test(before)) score += 4;\n      if (start <= 12) score += 1;\n      if (words.length <= 10) score += 1;\n      const prefix = semanticPrefixBeforeQuote(description, start);\n      // A malformed caption fragment plus an explicit labelled quoted work and\n      // nearby activity-format evidence is strong enough to recover the work\n      // title. This stays generic: no source, city, venue or event name is\n      // special-cased.\n      if (titleLooksLikeCaptionFragment(event) && prefix && hasActivityEvidence) score += 4;\n      if (score >= 5) {\n        candidates.push({ candidate: prefix ? `${prefix}: ${candidate}` : candidate, score: prefix ? score + 1 : score, start });\n      }\n'''
if text.count(old) != 1:
    raise SystemExit(f'caption score marker count={text.count(old)}')
p.write_text(text.replace(old, new, 1), encoding='utf-8')
print('GIJON_CAPTION_RECOVERY_SCORE_PATCH_APPLIED')
