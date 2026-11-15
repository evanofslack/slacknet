POSTGRES_USER=postgres
POSTGRES_PW=postgres
POSTGRES_DB=analogdb
POSTGRES_HOST=postgres
S3_REGION=us-east-1
S3_ENDPOINT=s3.wasabisys.com
S3_ACCESS_KEY_ID=KAWAYIK4C3V5DQLL3EZ9
S3_SECRET_ACCESS_KEY={{ op://Homelab/dorp-postgres-backup-s3/S3_SECRET_ACCESS_KEY }}
S3_BUCKET=analogdb-postgres-backup
S3_PREFIX=postgres
PASSPHRASE={{ op://Homelab/dorp-postgres-backup-s3/PASSPHRASE }}
SLACK_WEBHOOK_URL={{ op://Homelab/dorp-postgres-backup-s3/SLACK_WEBHOOK_URL }}

