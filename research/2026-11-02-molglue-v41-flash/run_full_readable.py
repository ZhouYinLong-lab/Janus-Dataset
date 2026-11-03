"""Run one readable-XML batch after validating the offline shadow gate.

This is a separate entry point so historical frozen runtime manifests and the
legacy ``batch_candidate.py`` command remain byte-stable.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
EXTRACTION = HERE.parent / "2026-10-25-api-extraction"
if str(EXTRACTION) not in sys.path:
    sys.path.insert(0, str(EXTRACTION))

from api import check_config  # noqa: E402
from candidate_runtime import run  # noqa: E402
from corpus import read, sha  # noqa: E402
from sentence_export import export  # noqa: E402
from sentence_workflow import request_for, validate_response  # noqa: E402
from sentence_workspace import verify  # noqa: E402


def _load_gate(path: Path):
    spec = importlib.util.spec_from_file_location("molglue_offline_gate", HERE / "offline_gate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate_gate(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--gate", required=True, type=Path)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--max-new-requests", type=int)
    parser.add_argument("--network-route", choices=["environment", "direct"], default="environment")
    parser.add_argument("--resume-operator-pause", action="store_true")
    args = parser.parse_args(argv)

    gate = _load_gate(args.gate)
    workspace = args.workspace.resolve()
    config = read(args.config)
    check_config(config)
    manifest = verify(workspace)
    if manifest.get("pipeline") != "molgluedb_sentence_v3":
        raise ValueError("full_readable_requires_sentence_protocol")
    run(workspace, config, args.ledger, request_for, validate_response,
        live=args.live, env_file=args.env_file,
        max_new_requests=args.max_new_requests,
        resume_operator_pause=args.resume_operator_pause,
        phase="full", on_progress=export, network_route=args.network_route)
    summary = export(workspace)
    result = {
        "gate": {"path": str(args.gate.resolve()), "sha256": sha(args.gate),
                 "status": gate["status"]},
        "workspace": str(workspace),
        "ledger": str(args.ledger.resolve()),
        "summary": summary,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
