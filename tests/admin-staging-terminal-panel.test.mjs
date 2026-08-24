import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const html = fs.readFileSync(new URL('../admin-staging/index.html', import.meta.url), 'utf8');

test('admin staging reads only the durable canonical terminal state', () => {
  assert.match(html, /state\/publication-terminal\/data\/publication_terminal_state\.json/);
  assert.match(html, /canonical-publication-terminal-state/);
  assert.match(html, /PUBLICATION_COMPLETE/);
  assert.match(html, /PUBLICATION_FAILED/);
  assert.doesNotMatch(html, /agenda_web\.json/);
});

test('panel exposes operational evidence without write capability', () => {
  for (const marker of ['Public SHA', 'Source ref', 'Publisher run', 'Finalizer run', 'Fast-close', 'Terminal ID']) {
    assert.ok(html.includes(marker), `missing ${marker}`);
  }
  assert.match(html, /cache:\s*'no-store'/);
  assert.match(html, /noindex,nofollow,noarchive/);
  assert.doesNotMatch(html, /method:\s*['"](?:POST|PUT|PATCH|DELETE)['"]/i);
});

test('load failures are not misreported as publication failures', () => {
  assert.match(html, /ESTADO NO DISPONIBLE/);
  assert.match(html, /Un fallo de carga no se interpreta como fallo de publicación/);
});
