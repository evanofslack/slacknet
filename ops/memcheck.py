"""Read-only memory check across all inventory hosts, for right-sizing VMs.

    cd ops && uv run --no-env-file python memcheck.py [host ...]

Reads /proc/meminfo over SSH (agent auth, ~/.ssh/config ignored, same as
inventory.py). "used" is MemTotal - MemAvailable, i.e. what the host actually
needs, excluding reclaimable page cache. "suggest" is a rough allocation:
used x 1.5, at least used + 2 GiB, rounded up to a whole GiB. It's a snapshot,
so check at a busy time too before shrinking anything.
"""

import math
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import inventory

GiB = 1024**3


def _hosts():
    hosts = inventory.vms + inventory.pis + inventory.vps
    # The Proxmox host isn't a pyinfra target; include it if MS02_IP is set.
    if inventory.ENV.get("MS02_IP"):
        hosts.append(inventory._host("ms02", ""))
    return hosts


def _meminfo(name: str, data: dict) -> tuple[str, dict | str]:
    cmd = [
        "ssh", "-F", "/dev/null",
        "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
        "-o", "IdentitiesOnly=no",
        "-p", str(data.get("ssh_port", 22)),
        f"{data['ssh_user']}@{data['ssh_hostname']}",
        "cat /proc/meminfo",
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    except subprocess.TimeoutExpired:
        return name, "timeout"
    if out.returncode != 0:
        return name, (out.stderr.strip().splitlines() or ["ssh failed"])[-1]
    info = {}
    for line in out.stdout.splitlines():
        key, _, rest = line.partition(":")
        if rest.split():
            info[key] = int(rest.split()[0]) * 1024  # kB -> bytes
    return name, info


def _row(name: str, m: dict) -> list[str]:
    total, avail = m["MemTotal"], m["MemAvailable"]
    used = total - avail
    swap_used = m.get("SwapTotal", 0) - m.get("SwapFree", 0)
    suggest = math.ceil(max(used * 1.5, used + 2 * GiB) / GiB)
    flag = ""
    if avail / total < 0.10 or swap_used > 0.5 * max(m.get("SwapTotal", 0), 1):
        flag = "TIGHT"
    elif suggest * GiB < total * 0.6:
        flag = "oversized"
    return [
        name,
        f"{total / GiB:.1f}",
        f"{used / GiB:.1f}",
        f"{avail / GiB:.1f}",
        f"{100 * used / total:.0f}%",
        f"{swap_used / GiB:.1f}/{m.get('SwapTotal', 0) / GiB:.1f}",
        f"{suggest}",
        flag,
    ]


def main(only: list[str]) -> None:
    hosts = [h for h in _hosts() if not only or h[0] in only]
    with ThreadPoolExecutor(max_workers=len(hosts) or 1) as pool:
        results = list(pool.map(lambda h: _meminfo(*h), hosts))

    header = ["host", "total", "used", "avail", "used%", "swap", "suggest", ""]
    rows, errors = [], []
    for name, m in results:
        (errors.append((name, m)) if isinstance(m, str) else rows.append(_row(name, m)))

    widths = [max(len(r[i]) for r in [header, *rows]) for i in range(len(header))]
    print("  ".join(h.ljust(w) for h, w in zip(header, widths)) + "   (GiB)")
    for r in rows:
        print("  ".join(c.rjust(w) if i else c.ljust(w) for i, (c, w) in enumerate(zip(r, widths))))
    for name, err in errors:
        print(f"{name}: unreachable ({err})", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:])
