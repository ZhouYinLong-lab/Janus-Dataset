import json
import importlib.util
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("generic_pipeline_under_test", Path(__file__).parent / "pipeline.py")
pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pipeline)
ADAPTER = Path(__file__).parents[1] / "阴性证据领域适配器" / "enzyme_engineering.json"


class GenericPipelineTests(unittest.TestCase):
    def test_prepare_and_validate_quote_grounding(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paper = root / "paper.txt"
            paper.write_text(
                "Variant X (A123V) showed 8% conversion of substrate Y, much lower than the parent enzyme.\n\n"
                "Variant Z was not tested on substrate Q.", encoding="utf-8"
            )
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps([{"paper_id": "P1", "path": str(paper)}]), encoding="utf-8")
            workspace = root / "workspace"
            pipeline.prepare(type("Args", (), {
                "manifest": manifest, "adapter": ADAPTER, "out": workspace,
                "max_chars": 8000, "max_units": 3,
            })())
            job_id = json.loads((workspace / "manifest.json").read_text(encoding="utf-8"))["job_ids"][0]
            job = json.loads((workspace / "jobs" / f"{job_id}.json").read_text(encoding="utf-8"))
            sid = job["sentences"][0]["sentence_id"]
            quote = job["sentences"][0]["text"]
            adapter_obj = json.loads((workspace / "adapter.json").read_text(encoding="utf-8"))
            values = {f: None for f in adapter_obj["fields"]}
            values.update({
                "enzyme_or_variant": "Variant X",
                "mutation": "A123V",
                "reaction_or_substrate": "substrate Y",
                "product_or_endpoint": "conversion",
                "result_value": "8",
                "unit": "% conversion",
                "observation": "low conversion compared with the parent",
            })
            evidence = {f: [] for f in adapter_obj["fields"]}
            for field in ["enzyme_or_variant", "mutation", "reaction_or_substrate", "product_or_endpoint", "result_value", "unit", "observation"]:
                evidence[field] = [{"sentence_id": sid, "quote": quote}]
            response = {
                "schema_version": 1, "job_id": job_id, "paper_id": "P1",
                "status": "observations", "records": [{
                    "record_id": "C1-R1", "outcome_type": "low_activity",
                    "values": values, "evidence": evidence, "qualifiers": [],
                }], "coverage_notes": [],
            }
            result = pipeline.validate_response(response, job, adapter_obj)
            self.assertEqual(len(result["accepted"]), 1)
            self.assertEqual(result["rejected"], [])
            self.assertTrue(result["accepted"][0]["ready_for_training"])

    def test_not_tested_is_not_training_ready_negative(self):
        adapter = pipeline.load_adapter(ADAPTER)
        job = {
            "job_id": "J1", "paper_id": "P1", "doi": None, "source_path": "paper.txt",
            "source_sha256": "x", "sentences": [{"sentence_id": "S1", "text": "Variant Z was not tested on substrate Q."}],
        }
        values = {f: None for f in adapter["fields"]}
        values.update({"enzyme_or_variant": "Variant Z", "reaction_or_substrate": "substrate Q",
                       "product_or_endpoint": "activity", "observation": "not tested"})
        evidence = {f: [] for f in adapter["fields"]}
        for field in ["enzyme_or_variant", "reaction_or_substrate", "product_or_endpoint", "observation"]:
            evidence[field] = [{"sentence_id": "S1", "quote": job["sentences"][0]["text"]}]
        response = {"schema_version": 1, "job_id": "J1", "paper_id": "P1",
                    "status": "observations", "records": [{"record_id": "C1-R1", "outcome_type": "not_tested",
                    "values": values, "evidence": evidence, "qualifiers": []}], "coverage_notes": []}
        result = pipeline.validate_response(response, job, adapter)
        self.assertEqual(len(result["accepted"]), 1)
        self.assertFalse(result["accepted"][0]["ready_for_training"])


if __name__ == "__main__":
    unittest.main()
