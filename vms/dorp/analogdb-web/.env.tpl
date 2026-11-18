NODE_ENV=production
NODE_BASE_URL=https://api.analogdb.com
API_BASE_URL=http://analogdb:8080/v1

# analogdb rate limit profiles

API_WEB_USERNAME={{ op://Homelab/dorp-analogdb-web/API_WEB_USERNAME }}
API_WEB_PASSWORD={{ op://Homelab/dorp-analogdb-web/API_WEB_PASSWORD }}
API_ADMIN_USERNAME={{ op://Homelab/dorp-analogdb-web/API_ADMIN_USERNAME }}
API_ADMIN_PASSWORD={{ op://Homelab/dorp-analogdb-web/API_ADMIN_PASSWORD }}

# nextjs admin login
ADMIN_USERNAME={{ op://Homelab/dorp-analogdb-web/ADMIN_USERNAME }}
ADMIN_PASSWORD={{ op://Homelab/dorp-analogdb-web/ADMIN_PASSWORD }}
ADMIN_SECRET={{ op://Homelab/dorp-analogdb-web/ADMIN_SECRET }}

GRAFANA_URL={{ op://Homelab/dorp-analogdb-web/GRAFANA_URL }}
DAGSTER_URL={{ op://Homelab/dorp-analogdb-web/DAGSTER_URL }}
