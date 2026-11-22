POSTGRES_USER={{ op://Homelab/dorp-analogdb-dagster/POSTGRES_USER }}
POSTGRES_PASSWORD={{ op://Homelab/dorp-analogdb-dagster/POSTGRES_PASSWORD }}
POSTGRES_DB=dagster
POSTGRES_PORT=5432

DAGSTER_LOG_LEVEL=DEBUG
DAGSTER_S3_ENDPOINT_URL=https://s3.us-east-1.amazonaws.com 
DAGSTER_S3_ACCESS_KEY={{ op://Homelab/dorp-analogdb-dagster/DAGSTER_S3_ACCESS_KEY }}
DAGSTER_S3_SECRET_KEY={{ op://Homelab/dorp-analogdb-dagster/DAGSTER_S3_SECRET_KEY }}
DAGSTER_S3_BUCKET=analogdb-dagster
DAGSTER_S3_LOG_BUCKET=analogdb-dagster-logs
DAGSTER_S3_PREFIX=dagster

AWS_ACCESS_KEY_ID={{ op://Homelab/dorp-analogdb-dagster/AWS_ACCESS_KEY_ID }}
AWS_SECRET_ACCESS_KEY={{ op://Homelab/dorp-analogdb-dagster/AWS_SECRET_ACCESS_KEY }}
AWS_REGION=us-east-1

REDDIT_CLIENT_ID={{ op://Homelab/dorp-analogdb-dagster/REDDIT_CLIENT_ID }}
REDDIT_CLIENT_SECRET={{ op://Homelab/dorp-analogdb-dagster/REDDIT_CLIENT_SECRET }}
REDDIT_USER_AGENT={{ op://Homelab/dorp-analogdb-dagster/REDDIT_USER_AGENT }}

ANALOGDB_USERNAME="{{ op://Homelab/dorp-analogdb-dagster/ANALOGDB_USERNAME }}"
ANALOGDB_PASSWORD="{{ op://Homelab/dorp-analogdb-dagster/ANALOGDB_PASSWORD }}"
ANALOGDB_SLACK_WEBHOOK_URL={{ op://Homelab/dorp-analogdb-dagster/ANALOGDB_SLACK_WEBHOOK_URL }}
ANALOGDB_ENDPOINT=http://analogdb:8080
ANALOGDB_LOG_LEVEL="debug"
ANALOGDB_APP_ENV="prod"
ANALOGDB_BATCH_POSTS_COUNT=100

OPENROUTER_API_KEY={{ op://Homelab/dorp-analogdb-dagster/OPENROUTER_API_KEY }}
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=google/gemini-2.5-flash-lite
OPENROUTER_VISION_MODEL=google/gemini-2.5-flash
