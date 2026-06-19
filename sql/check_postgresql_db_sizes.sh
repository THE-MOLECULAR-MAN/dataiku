#!/usr/bin/env bash
# Reports PostgreSQL database and table sizes; lists row counts per table.
# set -e is intentionally omitted: individual psql commands may fail (e.g. permission denied
# on a specific database) and we want the remaining databases to still be reported.
set -uo pipefail

# Replace with your installed PostgreSQL major version.
PSQL_VERSION="18"

sudo -u postgres psql -t -c "show data_directory;"

sudo du -sh /var/lib/postgresql/*

# List each database and each table sorted by size (largest first).
sudo -u postgres bash -c "for db in \$(psql -tAc 'SELECT datname FROM pg_database WHERE datistemplate = false'); do echo -e '\n=== Database: '\$db' ==='; psql -d \"\$db\" -Atc \"SELECT current_database() AS db, schemaname || '.' || relname AS table, pg_size_pretty(pg_total_relation_size(relid)) AS size FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC;\"; done"

# List each database and each table sorted by row count (most rows first).
sudo -u postgres bash -c "for db in \$(psql -tAc 'SELECT datname FROM pg_database WHERE datistemplate = false'); do echo -e '\n=== Database: '\$db' ==='; psql -d \"\$db\" -Atc \"SELECT current_database() AS db, schemaname || '.' || relname AS table, n_live_tup AS row_count FROM pg_stat_user_tables ORDER BY n_live_tup DESC;\"; done"

# To inspect or tune PostgreSQL settings, open the config file manually:
#   vim /etc/postgresql/${PSQL_VERSION}/main/postgresql.conf
