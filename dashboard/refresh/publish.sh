#!/bin/sh
set -eu

DASHBOARD_RELEASE=$(node -p "require('node:crypto').randomBytes(16).toString('hex')")
export DASHBOARD_RELEASE
sed -i "s@^  basePath: /dashboard\$@  basePath: /dashboard/releases/$DASHBOARD_RELEASE@" evidence.config.yaml
grep -Fxq "  basePath: /dashboard/releases/$DASHBOARD_RELEASE" evidence.config.yaml
npx evidence sources
# Evidence can emit query errors and still exit successfully.
build_log=$(mktemp)
trap 'rm -f "$build_log"' EXIT
if ! npx evidence build >"$build_log" 2>&1; then
  cat "$build_log"
  exit 1
fi
cat "$build_log"
if grep -Fq 'Error in Query!' "$build_log"; then
  echo 'Evidence query errors prevented dashboard publication.' >&2
  exit 1
fi
node refresh/upload.mjs
