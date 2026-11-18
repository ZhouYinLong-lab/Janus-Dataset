import importlib.util
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


MODULE_PATH = Path(__file__).with_name("mg2act_ml.py")
SPEC = importlib.util.spec_from_file_location("mg2act_ml", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class MG2ActMLTests(unittest.TestCase):
    def test_sequence_features_have_fixed_dimension(self):
        vector = MODULE.seq_features("ACDX")
        self.assertEqual(vector.shape, (21,))
        self.assertAlmostEqual(float(vector[0]), 0.25)

    def test_feature_vocabulary_is_train_only(self):
        train = pd.DataFrame({
            "Molecule_SMILES": ["CC"],
            "PrimaryTarget": ["T1"],
            "RecruitingProtein": ["E1"],
            "Target_seq": ["ACDE"],
            "E3_seq": ["ACDE"],
        })
        test = train.copy()
        test.loc[0, "PrimaryTarget"] = "unseen"
        builder = MODULE.FeatureBuilder(fp_size=32).fit(train)
        x_train = builder.transform(train)
        x_test = builder.transform(test)
        self.assertEqual(x_train.shape, x_test.shape)
        self.assertEqual(builder.categories.categories_[0].tolist(), ["T1"])

    def test_predictions_are_clipped_for_metrics(self):
        result = MODULE.metrics(
            np.asarray([0.0, 1.0]),
            np.asarray([-2.0, 4.0]),
            pd.Series(["T", "T"]),
        )
        self.assertEqual(result["mae"], 0.0)

    def test_model_grids_are_fixed(self):
        grids = MODULE.grids()
        self.assertEqual(set(grids), {"ridge", "extra_trees", "mlp"})
        self.assertEqual(MODULE.SEEDS, (20261029, 20261030, 20261031))


if __name__ == "__main__":
    unittest.main()
