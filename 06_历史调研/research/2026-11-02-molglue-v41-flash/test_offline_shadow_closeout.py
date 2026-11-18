import json
import tempfile
import unittest
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from offline_shadow_closeout import _normalize_content  # noqa: E402


class OfflineShadowCloseoutTests(unittest.TestCase):
    def test_identical_duplicate_keys_are_normalized(self):
        payload, repairs = _normalize_content('{"status":"x","reason":null,"reason":null}')
        self.assertEqual(payload, {"status": "x", "reason": None})
        self.assertEqual(repairs, ["reason"])

    def test_non_identical_duplicate_keys_are_rejected(self):
        with self.assertRaises(ValueError):
            _normalize_content('{"reason":null,"reason":"changed"}')

    def test_provider_wrapper_is_removed(self):
        payload, repairs = _normalize_content('{"type":"json_object","items":[]}')
        self.assertEqual(payload, {"items": []})
        self.assertIn("provider_wrapper:type", repairs)


if __name__ == "__main__":
    unittest.main()
