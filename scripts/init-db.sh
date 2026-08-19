#!/bin/sh
set -eu
psql --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=runtime_password="$NOTES_RUNTIME_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE notes_runtime LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS', :'runtime_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'notes_runtime')\gexec
GRANT CONNECT ON DATABASE notes TO notes_runtime;
GRANT USAGE ON SCHEMA public TO notes_runtime;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO notes_runtime;
SQL
