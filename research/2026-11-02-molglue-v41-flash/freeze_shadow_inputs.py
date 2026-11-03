"""Freeze the original shadow ledger without rewriting its append-only ledger.

Repair workspaces may share an append-only ledger.  This utility creates a
read-only snapshot containing only attempts owned by the original workspace,
so acceptance reports do not mix repair traffic with the frozen batch.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
EXTRACTION = HERE.parent / "2026-10-25-api-extraction"
if str(EXTRACTION) not in sys.path:
    sys.path.insert(0, str(EXTRACTION))

from corpus import read, save, sha  # noqa: E402


def freeze(ledger_path: Path, workspace: Path, out_ledger: Path, out_report: Path):
    ledger_path = Path(ledger_path).resolve()
    workspace = Path(workspace).resolve()
    out_ledger = Path(out_ledger).resolve()
    out_report = Path(out_report).resolve()
    ledger = read(ledger_path)
    owner = str(workspace)
    attempts = [a for a in ledger.get("attempts", [])
                if str(Path(a.get("workspace", "")).resolve()) == owner]
    if not attempts:
        raise ValueError(f"No ledger attempts belong to {workspace}")
    statuses = {a.get("status") for a in attempts}
    if "in_flight" in statuses:
        raise ValueError("Cannot freeze a ledger containing in-flight original attempts")
    frozen = dict(ledger)
    frozen["attempts"] = attempts
    frozen["frozen_from_ledger"] = str(ledger_path)
    frozen["frozen_workspace"] = owner
    frozen["frozen_attempt_count"] = len(attempts)
    frozen["repair_attempts_excluded"] = len(ledger.get("attempts", [])) - len(attempts)
    out_ledger.parent.mkdir(parents=True, exist_ok=True)
    save(out_ledger, frozen)
    report = {
        "source_ledger": str(ledger_path),
        "source_ledger_sha256": sha(ledger_path),
        "workspace": owner,
        "workspace_manifest_sha256": sha(workspace / "manifest.json"),
        "frozen_ledger": str(out_ledger),
        "frozen_ledger_sha256": sha(out_ledger),
        "frozen_attempts": len(attempts),
        "excluded_repair_attempts": frozen["repair_attempts_excluded"],
        "statuses": {status: sum(a.get("status") == status for a in attempts)
                     for status in sorted(statuses)},
        "append_only_source_preserved": True,
    }
    save(out_report, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--out-ledger", required=True, type=Path)
    parser.add_argument("--out-report", required=True, type=Path)
    args = parser.parse_args(argv)
    import json
    print(json.dumps(freeze(args.ledger, args.workspace, args.out_ledger, args.out_report),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
