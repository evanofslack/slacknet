#!/bin/bash
set -e

echo "Starting daily sync at $(date)"

# Password for prod
export PGPASSWORD="$POSTGRES_PROD_PASSWORD"

# Dump production
pg_dump -h "$POSTGRES_PROD_HOST" \
        -U "$POSTGRES_PROD_USER" \
        -d "$POSTGRES_PROD_DB" \
        --verbose \
        --clean \
        --no-owner \
        --no-privileges \
        --exclude-table-data='*_logs' \
        --exclude-table-data='*_temp' \
        > /tmp/daily_dump.sql

# Password for dev
export PGPASSWORD="$POSTGRES_DEV_PASSWORD"

# Restore dev
psql -h "$POSTGRES_DEV_HOST" \
     -U "$POSTGRES_DEV_USER" \
     -d "$POSTGRES_DEV_DB" \
     < /tmp/daily_dump.sql

echo "Daily sync completed successfully at $(date)"
rm /tmp/daily_dump.sql
