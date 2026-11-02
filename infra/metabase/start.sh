#!/bin/sh
set -eu
# Consume the existing Neon integration variables without copying secrets into code.
if [ -z "${MB_DB_CONNECTION_URI:-}" ] && [ -n "${PGHOST_UNPOOLED:-${PGHOST:-}}" ] && [ -n "${PGDATABASE:-}" ]; then
    export MB_DB_CONNECTION_URI="jdbc:postgresql://${PGHOST_UNPOOLED:-$PGHOST}:5432/${PGDATABASE}?sslmode=require"
    export MB_DB_USER="${PGUSER:?Neon user is missing}"
    export MB_DB_PASS="${PGPASSWORD:?Neon password is missing}"
fi
# Refuse ephemeral storage and never print connection strings.
case "${MB_DB_CONNECTION_URI:-}" in
    jdbc:postgresql://*) ;;
    *) printf '%s\n' 'Configure persistent PostgreSQL using MB_DB_CONNECTION_URI (JDBC format).' >&2; exit 78 ;;
esac
export MB_DB_TYPE=postgres
export MB_JETTY_PORT=3001
exec python3 /cp2/proxy.py
