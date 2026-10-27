import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import codex_io
from corpus import read, save, sha


class CodexIoTests(unittest.TestCase):
    def manifest(self, root):
        source = root / "source.xml"
        source.write_text("<article>source</article>", encoding="utf-8")
        job = root / "jobs" / "J1.json"
        job.parent.mkdir()
        save(job, {"job_id": "J1", "paper_id": "P1", "paragraphs": [], "sentences": []})
        document = root / "documents" / "P1.json"
        index = root / "sentence_indexes" / "P1.json"
        document.parent.mkdir(); index.parent.mkdir()
        save(document, {"paper_id": "P1", "source_sha256": sha(source), "units": []})
        save(index, [])
        manifest = {"pipeline": codex_io.PIPELINE, "papers": [{
            "paper_id": "P1", "doi": "10.1/p1", "title": "P1",
            "source_path": str(source), "source_sha256": sha(source),
            "source_kind": "xml", "document_path": str(document),
            "sentence_index_path": str(index), "sentence_count": 0,
            "sentence_gaps": [], "job_ids": ["J1"]}], "job_ids": ["J1"]}
        save(root / "manifest.json", manifest)
        return manifest

    def test_export_and_idempotent_import_and_source_guard(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "workspace"; root.mkdir()
            manifest = self.manifest(root)
            out = Path(tmp) / "package"
            with patch.object(codex_io, "verify", return_value=manifest):
                package_result = codex_io.export_task_package(root, out)
            self.assertEqual(package_result["tasks"], 1)
            package = read(out / "task_package.json")
            task = package["tasks"][0]
            incoming = Path(tmp) / "incoming"; incoming.mkdir()
            result = {"accepted": [], "rejected": [], "unresolved": [], "accounting_complete": True}
            row = {"task_id": task["task_id"], "paper_id": "P1", "stage": "discovery",
                   "source_sha256": task["source_sha256"], "result": result,
                   "raw_output": {"choices": []}, "generation_method": "Codex subagent"}
            save(incoming / "r.json", row)
            imported = codex_io.import_results(root, out / "task_package.json", incoming, out / "import")
            self.assertEqual(imported["imported"], 1)
            again = codex_io.import_results(root, out / "task_package.json", incoming, out / "import")
            self.assertEqual(again["duplicates"], 1)
            bad = dict(row, source_sha256="changed")
            save(incoming / "bad.json", bad)
            rejected = codex_io.import_results(root, out / "task_package.json", incoming / "bad.json", out / "import")
            self.assertEqual(rejected["rejected"], 1)


if __name__ == "__main__":
    unittest.main()
