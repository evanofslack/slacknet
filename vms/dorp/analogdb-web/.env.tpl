NODE_ENV=production
NODE_BASE_URL=https://api.analogdb.com
API_BASE_URL=http://analogdb:8080/v1

# analogdb rate limit profiles
# API_WEB_USERNAME=usernameforlimiting
# API_WEB_PASSWORD=  # old value removed
# API_ADMIN_USERNAME=evan_analog_pics
# API_ADMIN_PASSWORD=  # old value removed

API_WEB_USERNAME=web
API_WEB_PASSWORD={{ op://Homelab/dorp-analogdb-web/API_WEB_PASSWORD }}
API_ADMIN_USERNAME=admin
API_ADMIN_PASSWORD={{ op://Homelab/dorp-analogdb-web/API_ADMIN_PASSWORD }}

# old analogdb profiles
# AUTH_USERNAME=evan_analog_pics
# AUTH_PASSWORD=  # old value removed

# nextjs admin login
ADMIN_USERNAME=eslack_admin
ADMIN_PASSWORD={{ op://Homelab/dorp-analogdb-web/ADMIN_PASSWORD }}
ADMIN_SECRET={{ op://Homelab/dorp-analogdb-web/ADMIN_SECRET }}

GRAFANA_URL=http://10.33.1.212:3000/d/es6lk2p/metrics?var-rate=1m&orgId=1&from=now-24h&to=now&timezone=browser&var-datasource=Prometheus&var-container=analogdb&var-container=postgres&var-container=redis&var-container=weaviate-i2v&var-container=analogdb-web&var-container=weaviate&var-container=dagster_webserver&var-container=dagster_daemon&var-container=dagster_postgres&var-quantile=0.5&refresh=30s
DAGSTER_URL=http://10.33.1.143:3001/overview/activity/timeline
