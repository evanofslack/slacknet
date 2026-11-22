"""Roll a stack's files back to a backup taken by apply.py.

Run via ../ops/restore <host> <stack> <ts> [--up]. Removes files apply added,
untars the backup into the original working dir; --up restarts the stack.
"""

import shlex

from pyinfra import host
from pyinfra.operations import server

name, ts = host.data.get("stack"), host.data.get("ts")
if not (name and ts):
    raise SystemExit("restore: need stack and ts")
b = f"$HOME/.slacknet-backups/{shlex.quote(str(ts))}"
n = shlex.quote(str(name))
cmd = (
    f"test -f {b}/{n}.tgz && wd=$(cat {b}/{n}.dir) && cd \"$wd\" && "
    f"if [ -f {b}/{n}.new ]; then while IFS= read -r f; do rm -f -- \"$f\"; done < {b}/{n}.new; fi && "
    f"tar xzf {b}/{n}.tgz"
)
if host.data.get("up"):
    cmd += f" && docker compose -p {n} up -d"
server.shell(name=f"{name}: restore files from {ts}", commands=[cmd])
