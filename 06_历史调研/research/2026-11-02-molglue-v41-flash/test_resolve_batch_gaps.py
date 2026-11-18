import unittest

from resolve_batch_gaps import CONTEXT_DECISIONS, PARAGRAPH_DECISIONS


class ResolveBatchGapsTests(unittest.TestCase):
    def test_all_offline_decisions_are_ineligible(self):
        self.assertEqual(len(PARAGRAPH_DECISIONS), 11)
        self.assertEqual(len(CONTEXT_DECISIONS), 4)
        self.assertEqual(CONTEXT_DECISIONS[("B204", "C:a93a4df69eebc0153e9754c4f7fb6658437c2e32fd38baec9adca9022d4488f3")][0], "resolved_context_from_supplement")


if __name__ == "__main__":
    unittest.main()
