#!/usr/bin/env bash
set -euo pipefail

OUT="_cloudflare_site"
rm -rf "$OUT"
mkdir -p "$OUT"

# Copy the deployable repository snapshot without Git metadata or CI internals.
find . -mindepth 1 -maxdepth 1 \
  ! -name '.git' \
  ! -name '.github' \
  ! -name "$OUT" \
  ! -name 'cloudflare-build.sh' \
  -exec cp -R {} "$OUT"/ \;

# This deployment is a parallel validation copy, not the canonical production site.
cat > "$OUT/_headers" <<'EOF'
/*
  X-Robots-Tag: noindex, nofollow
EOF

# Public Cloudflare entrypoint contract:
# - normal visits to vivamos.pages.dev/ enter the branded PWA at /app/;
# - the historical root WEB remains byte-addressable for the existing production
#   verification probes, which use explicit technical query markers;
# - direct files such as /index.html remain untouched for exact-byte attestation.
#
# Keeping this routing in the deploy artifact prevents a data publication from
# silently making the legacy root WEB the public landing experience again.
cat > "$OUT/_worker.js" <<'EOF'
const VERIFICATION_QUERY_KEYS = new Set(["periodo", "evento", "semantic", "smoke"]);

function isVerificationRequest(url) {
  for (const key of VERIFICATION_QUERY_KEYS) {
    if (url.searchParams.has(key)) return true;
  }
  return false;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/" && !isVerificationRequest(url)) {
      const target = new URL("/app/", url);
      target.search = url.search;
      return Response.redirect(target.toString(), 302);
    }
    return env.ASSETS.fetch(request);
  },
};
EOF

# Fail the build if the essential WEB/PWA entry points or root-routing contract are missing.
test -f "$OUT/index.html"
test -f "$OUT/_worker.js"
grep -q 'url.pathname === "/"' "$OUT/_worker.js"
grep -q 'new URL("/app/", url)' "$OUT/_worker.js"
test -f "$OUT/assets/root-agenda-bootstrap.mjs"
test -f "$OUT/app/index.html"
test -f "$OUT/app/manifest.webmanifest"
test -f "$OUT/app/service-worker.js"
test -f "$OUT/agenda_web.json"
test -f "$OUT/app/data/gijon/agenda_web.json"
test -f "$OUT/app/image-quality-guard.js"
test -f "$OUT/app/formation-cycle-classifier.js"
test -f "$OUT/app/artequin-session-correction.js"

echo "CLOUDFLARE_PREVIEW_BUILD_OK surfaces=web,app public_root=app"
