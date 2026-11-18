import json

import pytest

import review_import_v1 as importer


def test_jsonl_roundtrip(tmp_path):
    path = tmp_path / "rows.jsonl"
    rows = [{"evidence_id": "E1", "value": "μM"}, {"evidence_id": "E2"}]
    importer.write_jsonl(path, rows)
    assert importer.read_jsonl(path) == rows


def test_missing_review_result_fails(tmp_path):
    with pytest.raises(ValueError, match="Missing review result"):
        importer.read_jsonl(tmp_path / "missing.jsonl")
