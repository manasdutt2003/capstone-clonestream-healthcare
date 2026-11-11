"""python -m hcls.audit.verify - exit 1 if any gold output changed since the last audit run."""

from __future__ import annotations

import sys

from hcls.audit import audit_log


def main() -> int:
    changed = audit_log.verify()
    if changed:
        print("changed since the last audit run:", *changed, sep="\n  ")
        return 1
    print("all outputs match the audit manifest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
