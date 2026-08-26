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
# Touching this canonical build entry point is also the bounded recovery trigger when
# an App-authored public write cannot emit GitHub's normal push workflow event.
cat > "$OUT/_headers" <<'EOF'
/*
  X-Robots-Tag: noindex, nofollow
EOF

# Preserve both canonical publication surfaces: WEB at / and App at /app/.
# A root-to-App redirect would make WEB verification inspect the wrong shell.

# Fail the build if the essential WEB/PWA entry points are missing.
test -f "$OUT/index.html"
test -f "$OUT/assets/root-agenda-bootstrap.mjs"
test -f "$OUT/app/index.html"
test -f "$OUT/app/manifest.webmanifest"
test -f "$OUT/app/service-worker.js"
test -f "$OUT/agenda_web.json"
test -f "$OUT/app/data/gijon/agenda_web.json"
test -f "$OUT/app/image-quality-guard.js"
test -f "$OUT/app/formation-cycle-classifier.js"
test -f "$OUT/app/artequin-session-correction.js"

echo "CLOUDFLARE_PREVIEW_BUILD_OK surfaces=web,app"
