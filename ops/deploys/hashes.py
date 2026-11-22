"""Read-only: sha256 of every path the repo would write on this host.

Run via ../ops/diff. Writes .inventory/<host>/hashes.txt (missing files are absent).
"""

import os
import sys
import tempfile

from pyinfra import host
from pyinfra.operations import files, server

OPS_DIR = os.getcwd()
sys.path.insert(0, OPS_DIR)
from deploy.desired import target_paths  # noqa: E402

paths = target_paths(host.name)
listing = tempfile.NamedTemporaryFile("w", delete=False, prefix="slacknet-paths-", suffix=".txt")
listing.write("\n".join(paths) + "\n")
listing.close()

REMOTE_LIST = "/tmp/slacknet-paths.txt"
REMOTE_OUT = "/tmp/slacknet-hashes.txt"

files.put(name="Upload path list", src=listing.name, dest=REMOTE_LIST, mode="600")
server.shell(
    name="Hash target files",
    commands=[f"while IFS= read -r f; do [ -f \"$f\" ] && sha256sum \"$f\" 2>/dev/null || true; done < {REMOTE_LIST} > {REMOTE_OUT}"],
)
files.get(
    name="Fetch hashes",
    src=REMOTE_OUT,
    dest=os.path.join(OPS_DIR, "..", ".inventory", host.name, "hashes.txt"),
    force=True,
)
for p in (REMOTE_LIST, REMOTE_OUT):
    files.file(name=f"Remove {p}", path=p, present=False)
