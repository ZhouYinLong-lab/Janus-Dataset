import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("strict_pipeline_under_test", Path(__file__).parent / "pipeline.py")
pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pipeline)
ADAPTER = Path(__file__).parents[1] / "05_阴性证据领域适配器" / "enzyme_engineering.json"


def args(**values):
    return type("Args", (), values)()


class StrictPipelineTests(unittest.TestCase):
    def make_workspace(self, root, text, suffix=".txt"):
        paper = root / f"paper{suffix}"
        paper.write_text(text, encoding="utf-8")
        manifest = root / "manifest.json"
        manifest.write_text(json.dumps([{"paper_id": "P1", "path": str(paper)}]), encoding="utf-8")
        workspace = root / "workspace"
        pipeline.prepare(args(manifest=manifest, adapter=ADAPTER, out=workspace, max_chars=8000, max_units=3))
        job_id = pipeline.read_json(workspace / "manifest.json")["job_ids"][0]
        job = pipeline.read_json(workspace / "jobs" / f"{job_id}.json")
        return workspace, job

    def make_record(self, job, incremental_status="narrative_increment", record_kind="biochemical_observation",
                    outcome_type="low_activity"):
        adapter = pipeline.load_adapter(ADAPTER)
        sentence = job["sentences"][0]
        quote = sentence["text"]
        values = {field: None for field in adapter["fields"]}
        values.update({
            "enzyme_or_variant": "Variant X",
            "parent_enzyme": "parent enzyme",
            "mutation": "A123V",
            "reaction_or_substrate": "substrate Y",
            "product_or_endpoint": "conversion",
            "assay": "HPLC",
            "experimental_condition": "37 °C for 2 h",
            "result_value": "8",
            "unit": "% conversion",
            "observation": "8% conversion, lower than the parent",
        })
        evidence = {field: [] for field in adapter["fields"]}
        for field, value in values.items():
            if value is not None:
                evidence[field] = [{"sentence_id": sentence["sentence_id"], "quote": quote}]
        return {
            "record_id": "C1-R1", "outcome_type": outcome_type,
            "record_kind": record_kind, "incremental_status": incremental_status,
            "values": values, "evidence": evidence, "qualifiers": [],
        }

    def make_response(self, job, record):
        return {
            "schema_version": 2, "job_id": job["job_id"], "paper_id": job["paper_id"],
            "status": "observations", "records": [record], "coverage_notes": [],
        }

    def test_rule_scan_flags_non_target_failures_and_figure_links(self):
        html = """
        <h2>Results</h2>
        <p>Variant X produced no product from substrate Y under the tested reaction conditions.</p>
        <p>Attempts to locate a DFT transition state were unsuccessful.</p>
        <p>The enzymes could not be purified on an FPLC system.</p>
        <p>Variant Z showed low activity as summarized in Figure 2.</p>
        <h2>References</h2>
        <p>Previous studies reported no activity for another enzyme.</p>
        """
        with tempfile.TemporaryDirectory() as temp:
            workspace, _ = self.make_workspace(Path(temp), html, ".html")
            pipeline.scan(args(workspace=workspace))
            summary = pipeline.read_json(workspace / "candidate_summary.json")
            self.assertEqual(summary["eligible_for_review"], 1)
            self.assertGreaterEqual(summary["excluded_candidates"], 4)

    def test_structural_validation_never_marks_unreviewed_record_ready(self):
        text = "Variant X (A123V) showed 8% conversion of substrate Y by HPLC at 37 °C for 2 h, lower than the parent enzyme."
        with tempfile.TemporaryDirectory() as temp:
            workspace, job = self.make_workspace(Path(temp), text)
            result = pipeline.validate_response(self.make_response(job, self.make_record(job)), job, pipeline.load_adapter(ADAPTER))
            self.assertEqual(len(result["accepted"]), 1)
            self.assertFalse(result["accepted"][0]["ready_for_training"])
            self.assertIn("human_review_required", result["accepted"][0]["training_gate_reasons"])

    def test_human_adjudication_is_required_for_training_ready(self):
        text = "Variant X (A123V) showed 8% conversion of substrate Y by HPLC at 37 °C for 2 h, lower than the parent enzyme."
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace, job = self.make_workspace(root, text)
            response_path = workspace / "responses" / f"{job['job_id']}.json"
            pipeline.write_json(response_path, self.make_response(job, self.make_record(job)))
            pipeline.validate(args(workspace=workspace))
            validated = pipeline.read_json(workspace / "results" / f"{job['job_id']}.json")
            key = validated["accepted"][0]["record_key"]
            decisions = root / "decisions.json"
            pipeline.write_json(decisions, [{
                "record_key": key, "decision": "accepted", "reviewer": "human-reviewer",
                "reviewed_at": "2026-11-13", "record_kind": "biochemical_observation",
                "incremental_status": "narrative_increment", "notes": "Verified against narrative text.",
            }])
            pipeline.adjudicate(args(workspace=workspace, decisions=decisions))
            adjudicated = pipeline.read_json(workspace / "adjudicated" / f"{job['job_id']}.json")
            self.assertTrue(adjudicated["accepted"][0]["ready_for_training"])
            self.assertEqual(adjudicated["accepted"][0]["training_gate_reasons"], [])

    def test_figure_linked_and_non_biochemical_records_remain_blocked_after_review(self):
        text = "Variant X (A123V) showed 8% conversion of substrate Y by HPLC at 37 °C for 2 h, lower than the parent enzyme (Figure 2)."
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace, job = self.make_workspace(root, text)
            response_path = workspace / "responses" / f"{job['job_id']}.json"
            pipeline.write_json(response_path, self.make_response(
                job, self.make_record(job, incremental_status="figure_table_linked", record_kind="process_failure")
            ))
            pipeline.validate(args(workspace=workspace))
            validated = pipeline.read_json(workspace / "results" / f"{job['job_id']}.json")
            key = validated["accepted"][0]["record_key"]
            decisions = root / "decisions.json"
            pipeline.write_json(decisions, [{
                "record_key": key, "decision": "accepted", "reviewer": "human-reviewer",
                "reviewed_at": "2026-11-13", "record_kind": "process_failure",
                "incremental_status": "figure_table_linked", "notes": "Valid, but outside training scope.",
            }])
            pipeline.adjudicate(args(workspace=workspace, decisions=decisions))
            record = pipeline.read_json(workspace / "adjudicated" / f"{job['job_id']}.json")["accepted"][0]
            self.assertFalse(record["ready_for_training"])
            self.assertIn("record_kind_not_biochemical_training_target", record["training_gate_reasons"])
            self.assertIn("figure_table_reference_requires_resolution", record["training_gate_reasons"])

    def test_not_tested_cannot_be_training_ready(self):
        text = "Variant X was not tested on substrate Y under these conditions."
        with tempfile.TemporaryDirectory() as temp:
            workspace, job = self.make_workspace(Path(temp), text)
            record = self.make_record(job, outcome_type="not_tested")
            result = pipeline.validate_response(self.make_response(job, record), job, pipeline.load_adapter(ADAPTER))
            self.assertFalse(result["accepted"][0]["ready_for_training"])
            self.assertIn("outcome_not_training_negative", result["accepted"][0]["training_gate_reasons"])


if __name__ == "__main__":
    unittest.main()
