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

# Cloudflare's public root is the branded Vivamos PWA. Preserve the legacy
# root WEB shell under /web/ so production semantic/image verification can
# continue to exercise it without exposing a different visual identity at /.
mkdir -p "$OUT/web"
cp "$OUT/index.html" "$OUT/web/index.html"
cat > "$OUT/_redirects" <<'EOF'
/ /app/ 302
EOF

# Fail the build if the essential public/PWA and verification entry points are missing.
test -f "$OUT/index.html"
test -f "$OUT/web/index.html"
test -f "$OUT/_redirects"
grep -qx '/ /app/ 302' "$OUT/_redirects"
test -f "$OUT/assets/root-agenda-bootstrap.mjs"
test -f "$OUT/app/index.html"
test -f "$OUT/app/manifest.webmanifest"
test -f "$OUT/app/service-worker.js"
test -f "$OUT/agenda_web.json"
test -f "$OUT/app/data/gijon/agenda_web.json"
test -f "$OUT/app/image-quality-guard.js"
test -f "$OUT/app/formation-cycle-classifier.js"
test -f "$OUT/app/artequin-session-correction.js"

echo "CLOUDFLARE_PREVIEW_BUILD_OK public_root=app verification_web=/web/"
