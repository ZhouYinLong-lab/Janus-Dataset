import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("map_negative_evidence.py")
SPEC = importlib.util.spec_from_file_location("negative_mapping", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class NegativeMappingTests(unittest.TestCase):
    def test_doi_is_normalized(self):
        self.assertEqual(
            MODULE.normalize_doi("https://doi.org/10.1021/ABC"),
            "10.1021/abc",
        )

    def test_compound_list_matches_named_members(self):
        self.assertEqual(
            MODULE.name_match("compounds 21, 37 and 41", "37")[0],
            "explicit_numbered_member",
        )

    def test_identifier_prefix_is_not_a_match(self):
        self.assertIsNone(MODULE.name_match("FL2-14", "FL2")[0])

    def test_analogue_series_does_not_map_to_parent(self):
        self.assertIsNone(MODULE.name_match("SR-4835 analogues", "SR-4835")[0])

    def test_explicit_exclusion_does_not_match(self):
        self.assertIsNone(
            MODULE.name_match("all compounds other than ML 1-50", "ML 1-50")[0]
        )

    def test_compound_and_cmpd_are_equivalent(self):
        self.assertEqual(
            MODULE.name_match("compound 10", "cmpd 10")[0],
            "normalized_identifier",
        )

    def test_hyphenated_identifier_variant_matches(self):
        self.assertEqual(
            MODULE.name_match("TMX1", "TMX-1")[0],
            "normalized_identifier",
        )

    def test_numbered_range_expands_only_named_members(self):
        self.assertEqual(
            MODULE.name_match("analogues 32-35", "34")[0],
            "explicit_numbered_member",
        )
        self.assertIsNone(MODULE.name_match("analogues 32-35", "36")[0])

    def test_named_parent_is_not_used_for_analogue_series(self):
        self.assertIsNone(MODULE.name_match("SR-4835 analogues", "SR-4835")[0])

    def test_experiment_units_are_deduplicated(self):
        base = {
            "mapping_id": "a", "experiment_id": "x", "canonical_smiles": "CC",
            "target_normalized": "brd4", "outcome_type": "not_observed",
            "high_confidence": True, "match_confidence": 1.0,
        }
        duplicate = {**base, "mapping_id": "b", "match_confidence": 0.95}
        self.assertEqual(len(MODULE.deduplicate_units([duplicate, base])), 1)


if __name__ == "__main__":
    unittest.main()
