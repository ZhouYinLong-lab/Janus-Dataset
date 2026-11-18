import unittest

from utility_error_analysis import choose, comparison, reference_fields, strength_class


class UtilityErrorAnalysisTests(unittest.TestCase):
    def test_reference_fields_and_strength(self):
        fields = reference_fields("subject=A；endpoint=protein degradation；observation=less degradation")
        self.assertEqual(fields["endpoint"], "protein degradation")
        self.assertEqual(strength_class(fields), "relative_weakening")

    def test_comparison_keeps_missing(self):
        self.assertEqual(comparison(1, 0), "better")
        self.assertEqual(comparison(0, 1), "worse")
        self.assertEqual(comparison(None, 1), "missing")

    def test_case_selection_is_deterministic_and_caps_doi(self):
        rows = [{"question_id": f"q{i}", "doi": f"d{i // 2}"} for i in range(8)]
        first = choose(rows, 4, "s", set(), __import__("collections").Counter(), 7)
        second = choose(rows, 4, "s", set(), __import__("collections").Counter(), 7)
        self.assertEqual([x["question_id"] for x in first], [x["question_id"] for x in second])
        counts = __import__("collections").Counter(x["doi"] for x in first)
        self.assertLessEqual(max(counts.values()), 2)


if __name__ == "__main__":
    unittest.main()
