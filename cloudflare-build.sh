#!/usr/bin/env bash
set -euo pipefail

OUT="_cloudflare_site"
rm -rf "$OUT"
mkdir -p "$OUT"

find . -mindepth 1 -maxdepth 1 \
  ! -name '.git' \
  ! -name '.github' \
  ! -name "$OUT" \
  ! -name 'cloudflare-build.sh' \
  -exec cp -R {} "$OUT"/ \;

cat > "$OUT/_headers" <<'EOF'
/*
  X-Robots-Tag: noindex, nofollow
EOF

cat > "$OUT/_redirects" <<'EOF'
/ /app/?city=valparaiso 302
EOF

test -f "$OUT/index.html"
test -f "$OUT/app/index.html"
test -f "$OUT/app/manifest.webmanifest"
test -f "$OUT/app/service-worker.js"
test -f "$OUT/agenda_web.json"
test -f "$OUT/app/data/gijon/agenda_web.json"
test -f "$OUT/app/image-quality-guard.js"
test -f "$OUT/app/formation-cycle-classifier.js"
test -f "$OUT/app/registration-reminders.js"

echo "CLOUDFLARE_PREVIEW_BUILD_OK"
