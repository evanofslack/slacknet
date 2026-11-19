# you can change these if you want
POSTGRES_USER="{{ op://Homelab/nubuntu-expanse/POSTGRES_USER }}"
POSTGRES_PASSWORD="{{ op://Homelab/nubuntu-expanse/POSTGRES_PASSWORD }}"
POSTGRES_DB="db"
PSQL_CONNECTION="" # optional psql connection uri. if you provide this, expanse will use it instead of the above vars

# go to https://www.reddit.com/prefs/apps ➔ "create another app..." ➔ name: "expanse", type: "web app", redirect uri: "http://localhost:1301/callback". then fill in these values
REDDIT_USERNAME="{{ op://Homelab/nubuntu-expanse/REDDIT_USERNAME }}"
REDDIT_APP_ID="{{ op://Homelab/nubuntu-expanse/REDDIT_APP_ID }}"
REDDIT_APP_SECRET={{ op://Homelab/nubuntu-expanse/REDDIT_APP_SECRET }}
REDDIT_APP_REDIRECT="https://expanse.local.eslack.net/callback" # use this default value for host-device-only usage. change it to "http://{host ip}:1301/callback" for general LAN usage. if you are serving the app publicly, change it to "https://{your public domain}/callback"

# fill in username(s) (case-sensitive) separated by ", " (a comma AND a space) in the quotes. use "*" to allow or deny all, except usernames in the other list
ALLOWED_USERS="{{ op://Homelab/nubuntu-expanse/ALLOWED_USERS }}"
DENIED_USERS="*"

# fill each of these with a 30+ character secure string. e.g., you can generate it using `pwgen -scn 30 1`
SESSION_SECRET="{{ op://Homelab/nubuntu-expanse/SESSION_SECRET }}"
ENCRYPTION_KEY="{{ op://Homelab/nubuntu-expanse/ENCRYPTION_KEY }}"
