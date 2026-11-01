"""Host-side recipe-engine contracts; no manufacturer binary fixture required."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from a7m4 import awb_priority as awb


class AwbPriorityContracts(unittest.TestCase):
    def setUp(self):
        self.data = bytes(range(32))
        result = bytearray(self.data)
        result[4:8] = b"ABCD"
        result[12:16] = b"EFGH"
        self.result = bytes(result)
        self.profile = {
            "input_bytes": len(self.data),
            "identities": {awb.digest(self.data): {"output_sha256": awb.digest(self.result)}},
            "patches": [
                {"file_offset": "0x4", "before": self.data[4:8].hex(), "after": b"ABCD".hex()},
                {"file_offset": "0xc", "before": self.data[12:16].hex(), "after": b"EFGH".hex()},
            ],
        }

    def test_unknown_complete_identity_is_rejected(self):
        with self.assertRaises(ValueError):
            awb.patch_cp(self.data[:-1] + b"?", self.profile)

    def test_wrong_original_instruction_is_rejected(self):
        profile = copy.deepcopy(self.profile)
        profile["patches"][0]["before"] = b"????".hex()
        with self.assertRaises(ValueError):
            awb.patch_cp(self.data, profile)

    def test_overlap_is_rejected(self):
        profile = copy.deepcopy(self.profile)
        profile["patches"][1]["file_offset"] = "0x6"
        profile["patches"][1]["before"] = self.data[6:10].hex()
        with self.assertRaises(ValueError):
            awb.patch_cp(self.data, profile)

    def test_wrong_complete_output_identity_is_rejected(self):
        profile = copy.deepcopy(self.profile)
        profile["identities"][awb.digest(self.data)]["output_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            awb.patch_cp(self.data, profile)

    def test_cli_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder)/"source", Path(folder)/"output"
            source.write_bytes(self.data)
            output.write_bytes(b"keep")
            with patch.object(awb, "load_profile", return_value=self.profile), patch("sys.argv", ["awb", "--input", str(source), "--output", str(output)]):
                with self.assertRaises(FileExistsError):
                    awb.main()
            self.assertEqual(output.read_bytes(), b"keep")
            self.assertEqual(source.read_bytes(), self.data)


if __name__ == "__main__":
    unittest.main()
