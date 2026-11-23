"""Push repo files + rendered secrets into stacks' existing working dirs.

Run via ../ops/apply <host> --stack a,b [--up] [--create]. Per stack:
  1. back up the files about to be overwritten to ~/.slacknet-backups/<ts>/<stack>.tgz
     (and list the files that are new, so restore can remove them)
  2. upload every repo file (.env rendered with op inject, mode 600); never deletes
  3. only with --up: docker compose pull && up -d

A stack with no running compose project is refused unless --create, which deploys
it to the canonical ~/slacknet/<repo dir> (only affects stacks not yet deployed).
"""

import os
import shlex
import sys

from pyinfra import host
from pyinfra.operations import files, server

OPS_DIR = os.getcwd()
sys.path.insert(0, OPS_DIR)
from deploy.desired import canonical_dir, check_repo, plan, render  # noqa: E402

check_repo(bool(host.data.get("any_branch")))
want = [s for s in str(host.data.get("stacks") or "").split(",") if s]
if not want:
    raise SystemExit("apply: --stack is required")
ts = host.data.get("ts")
do_up = bool(host.data.get("up"))
do_create = bool(host.data.get("create"))

stacks, _ = plan(host.name)

# The repo points stack state at /srv/<stack>. Pushing that to a stack whose data is still in
# its compose dir would start it on empty dirs (now, or on the next restart): migrate first.
from reconcile.datadirs import plan_host  # noqa: E402

pending = plan_host(host.name)
blocked = [n for n in want if pending.get(n, {}).get("moves")]
if blocked:
    raise SystemExit(
        f"apply: {', '.join(blocked)} on {host.name} still have data in their stack dir (per the last "
        f"snapshot); run ops/migrate first (or ops/collect if they were already migrated)")
created = set()
for name in want:
    if name not in stacks:
        raise SystemExit(f"apply: unknown stack {name!r} on {host.name}")
    s = stacks[name]
    if not s.working_dir:
        if not do_create:
            raise SystemExit(f"apply: {name!r} is not deployed on {host.name} (no running project); pass --create to deploy it")
        s.working_dir = canonical_dir(host.name, s.repo_dir)
        created.add(name)
        print(f"apply: {name}: new stack, creating {s.working_dir}")

for name in want:
    s = render(stacks[name])
    wd = s.working_dir
    q = shlex.quote
    backup_dir = f"$HOME/.slacknet-backups/{ts}"
    rels = " ".join(q(r) for r in s.files)
    mkdir = f"mkdir -p {q(wd)} && " if name in created else ""
    server.shell(
        name=f"{name}: back up current files",
        commands=[
            f"mkdir -p {backup_dir} && chmod 700 $HOME/.slacknet-backups {backup_dir} && {mkdir}cd {q(wd)} && "
            f"for f in {rels}; do if [ -e \"$f\" ]; then echo \"$f\"; else echo \"$f\" >> {backup_dir}/{name}.new; fi; done "
            f"| tar czf {backup_dir}/{name}.tgz -T - && chmod 600 {backup_dir}/{name}.tgz && "
            f"echo {q(wd)} > {backup_dir}/{name}.dir"
        ],
    )
    for rel, secret in s.files.items():
        files.put(
            name=f"{name}: {rel}",
            src=str(s.local / rel),
            dest=f"{wd}/{rel}",
            mode="600" if rel == ".env" else None,
        )
    if do_up:
        fargs = " ".join(f"-f {q(f)}" for f in s.config_files)
        # relocated stacks: same config hash means compose would keep the old container,
        # still labeled with the deleted dir, so force it to be recreated from the new one
        recreate = " --force-recreate" if s.relocate_from else ""
        server.shell(
            name=f"{name}: docker compose pull && up -d{recreate}",
            commands=[f"cd {q(wd)} && docker compose -p {q(name)} {fargs} pull -q && docker compose -p {q(name)} {fargs} up -d{recreate}"],
        )
