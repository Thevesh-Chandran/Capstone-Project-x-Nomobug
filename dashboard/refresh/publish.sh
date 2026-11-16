#!/bin/sh
set -eu

DASHBOARD_RELEASE=$(node -p "require('node:crypto').randomBytes(16).toString('hex')")
export DASHBOARD_RELEASE
sed -i "s@^  basePath: /dashboard$@  basePath: /dashboard/releases/$DASHBOARD_RELEASE@" evidence.config.yaml
grep -Fxq "  basePath: /dashboard/releases/$DASHBOARD_RELEASE" evidence.config.yaml
npx evidence sources
npx evidence build
node refresh/upload.mjs
