import sample_omission_audit_v1 as sample


def test_sample_is_fixed_and_stratified():
    assert set(sample.SAMPLE) == {"low", "medium", "high"}
    assert all(len(rows) == 5 for rows in sample.SAMPLE.values())
    assert len({pid for rows in sample.SAMPLE.values() for pid in rows}) == 15
    assert sample.SEED == "20261027"
