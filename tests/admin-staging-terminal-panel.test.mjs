import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const html = fs.readFileSync(new URL('../admin-staging/index.html', import.meta.url), 'utf8');
const publish = fs.readFileSync(new URL('../.github/workflows/publish.yml', import.meta.url), 'utf8');

test('admin staging reads the durable canonical terminal state and permanent production history', () => {
  assert.match(html, /state\/publication-terminal\/data\/publication_terminal_state\.json/);
  assert.match(html, /state\/production-certifications\/data\/index\.json/);
  assert.match(html, /canonical-publication-terminal-state/);
  assert.match(html, /vivamos-production-certification-history/);
  assert.match(html, /environment\s*!==\s*'production'/);
  assert.match(html, /PUBLICATION_COMPLETE/);
  assert.match(html, /PUBLICATION_FAILED/);
  assert.doesNotMatch(html, /agenda_web\.json/);
});

test('production and PR preview are visually and semantically distinct', () => {
  assert.match(html, /PRODUCCIÓN CANÓNICA/);
  assert.match(html, /PREVIEW DE PR · NO PRODUCCIÓN/);
  assert.match(html, /Un preview nunca certifica ni invalida la producción/);
  assert.match(html, /“Build failed”/);
  assert.match(html, /data-environment="production"/);
  assert.match(html, /data-environment="preview"/);
});

test('panel exposes operational and immutable certification evidence without write capability', () => {
  for (const marker of [
    'Public SHA',
    'Source ref',
    'Publisher run',
    'Finalizer run',
    'Fast-close',
    'Terminal ID',
    'Historial permanente por release',
    'SHA certificado',
    'Production smoke',
    'Evidencia inmutable',
  ]) {
    assert.ok(html.includes(marker), `missing ${marker}`);
  }
  assert.match(html, /cache:\s*'no-store'/);
  assert.match(html, /noindex,nofollow,noarchive/);
  assert.doesNotMatch(html, /method:\s*['"](?:POST|PUT|PATCH|DELETE)['"]/i);
});

test('load failures are not misreported as publication or certification failures', () => {
  assert.match(html, /ESTADO NO DISPONIBLE/);
  assert.match(html, /HISTORIAL NO DISPONIBLE/);
  assert.match(html, /Un fallo de carga no se interpreta como fallo de publicación ni como fallo de certificación/);
});

test('admin staging and permanent certifications use the canonical production workflow', () => {
  assert.match(publish, /- "admin-staging\/\*\*"/);
  assert.match(publish, /name: sync-cloudflare/);
  assert.match(publish, /ref: state\/production-certifications/);
  assert.match(publish, /git -C \.production-certification-state push origin HEAD:state\/production-certifications/);
  assert.match(publish, /production_certification_history\.py/);
  assert.doesNotMatch(publish, /git\s+push\s+[^\n]*HEAD:main\b/);
  assert.doesNotMatch(publish, /admin-staging.*workflow_dispatch/);
});
