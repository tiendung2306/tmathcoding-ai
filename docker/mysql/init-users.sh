#!/bin/bash
set -euo pipefail

quote_sql() { printf '%s' "$1" | sed "s/'/''/g"; }
if [[ ! "$MYSQL_DATABASE" =~ ^[A-Za-z0-9_]{1,64}$ ]]; then
    echo "Invalid MYSQL_DATABASE" >&2
    exit 1
fi
app_user=$(quote_sql "$DATABASE_APP_USER")
app_password=$(quote_sql "$DATABASE_APP_PASSWORD")
if [[ "$DATABASE_ROLE" == "source" ]]; then
    grants="SELECT"
else
    grants="SELECT, INSERT, UPDATE, DELETE"
fi
MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --protocol=socket -uroot <<SQL
SET SESSION sql_mode = 'NO_BACKSLASH_ESCAPES';
CREATE USER IF NOT EXISTS '$app_user'@'%' IDENTIFIED BY '$app_password';
ALTER USER '$app_user'@'%' IDENTIFIED BY '$app_password';
REVOKE ALL PRIVILEGES, GRANT OPTION FROM '$app_user'@'%';
GRANT $grants ON \`$MYSQL_DATABASE\`.* TO '$app_user'@'%';
SQL
if [[ "$DATABASE_ROLE" == "dashboard" ]]; then
    migration_user=$(quote_sql "$DASHBOARD_MIGRATION_USER")
    migration_password=$(quote_sql "$DASHBOARD_MIGRATION_PASSWORD")
    MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --protocol=socket -uroot <<SQL
SET SESSION sql_mode = 'NO_BACKSLASH_ESCAPES';
CREATE USER IF NOT EXISTS '$migration_user'@'%' IDENTIFIED BY '$migration_password';
ALTER USER '$migration_user'@'%' IDENTIFIED BY '$migration_password';
REVOKE ALL PRIVILEGES, GRANT OPTION FROM '$migration_user'@'%';
GRANT ALL PRIVILEGES ON \`$MYSQL_DATABASE\`.* TO '$migration_user'@'%';
SQL
fi
