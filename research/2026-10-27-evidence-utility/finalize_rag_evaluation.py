"""Convert adjudications into the existing scoring contract and write the RAG report."""
import argparse
import json
from pathlib import Path

from common import read, write


def finalize(trial, packet, adjudications, out):
    adjudications = read(adjudications)
    judgments = []
    seen = set()
    for row in adjudications:
        jid = row["review_a_id"]
        if jid in seen:
            raise ValueError("Duplicate adjudication reviewer key")
        seen.add(jid)
        final = row["final_judgment"]
        judgments.append({"judge_id": jid, "judgment": {
            "criteria": final["criteria"],
            "overclaim": final["overclaim"],
            "citation_supported": final["citation_supported"],
            "judge": row.get("adjudicator", "model-assisted adjudicator; not expert gold"),
            "reason": json.dumps(row.get("decision_basis", {}), ensure_ascii=False),
        }})
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    write(out / "final_judgments.json", judgments)
    from evaluate import score
    result = score(trial, packet, out / "final_judgments.json", out / "scored")
    result["review_provenance"] = "Two independent Luna model-assisted screening passes plus model-assisted adjudication; not expert gold."
    result["judged_answers"] = len(judgments)
    result["generation_exceptions"] = {
        "historical_unknown": 1,
        "invalid_response": 1,
        "not_retried": True,
    }
    write(out / "rag_quality_report.json", result)
    return {"judged": len(judgments), "report": str(out / "rag_quality_report.json")}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--trial", required=True, type=Path)
    p.add_argument("--packet", required=True, type=Path)
    p.add_argument("--adjudications", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    print(json.dumps(finalize(**vars(p.parse_args())), ensure_ascii=False, indent=2))
