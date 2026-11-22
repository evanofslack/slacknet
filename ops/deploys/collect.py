"""Read-only inventory: run collect-host.sh on each host and fetch the tarball.

Run via ../ops/collect (it extracts the results and prints a summary).
"""

import os

from pyinfra import host
from pyinfra.operations import files, server

OPS_DIR = os.getcwd()  # the `collect` wrapper cd's into ops/
OUT_DIR = os.path.join(OPS_DIR, "..", ".inventory", "_tarballs")
os.makedirs(OUT_DIR, mode=0o700, exist_ok=True)

REMOTE_SCRIPT = "/tmp/slacknet-collect-host.sh"
REMOTE_TAR = "/tmp/slacknet-inventory.tar.gz"

files.put(
    name="Upload collect script",
    src=os.path.join(OPS_DIR, "files", "collect-host.sh"),
    dest=REMOTE_SCRIPT,
    mode="700",
)

server.shell(
    name="Collect host inventory",
    commands=[f"{REMOTE_SCRIPT} {REMOTE_TAR}"],
)

files.get(
    name="Fetch inventory tarball",
    src=REMOTE_TAR,
    dest=os.path.join(OUT_DIR, f"{host.name}.tar.gz"),
    force=True,
)

for path in (REMOTE_TAR, REMOTE_SCRIPT):
    files.file(name=f"Remove {path}", path=path, present=False)
