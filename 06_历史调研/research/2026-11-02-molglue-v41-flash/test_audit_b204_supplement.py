import unittest

from audit_b204_supplement import GSPT1_GT10, GSPT1_ND, TABLE_COMPOUNDS, _experiment_id


class B204SupplementAuditTests(unittest.TestCase):
    def test_nd_is_not_converted_to_negative(self):
        self.assertEqual(set(TABLE_COMPOUNDS), GSPT1_GT10 | GSPT1_ND)
        self.assertFalse(GSPT1_GT10 & GSPT1_ND)
        self.assertIn("7", GSPT1_ND)
        self.assertIn("8", GSPT1_GT10)

    def test_table_and_figure_mentions_share_experiment_identity(self):
        self.assertEqual(_experiment_id("21", "IKZF1"), "B204:supplement:21:IKZF1:24h")


if __name__ == "__main__":
    unittest.main()
