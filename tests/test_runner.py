import json
from pathlib import Path
import subprocess
import sys
import unittest

from clinic.runner import replay, unique_object
from tools.build import build


class RunnerTests(unittest.TestCase):
    def test_packaged_cli_matches_source_in_fresh_working_directory(self):
        artifact = build()
        first = artifact.read_bytes()
        self.assertEqual(first, build().read_bytes())
        # Repository parent contains no importable clinic package.
        report = json.loads(subprocess.check_output([sys.executable, "-I", str(artifact)], cwd=artifact.parents[2]))
        self.assertEqual(replay(), report)
        self.assertEqual(28, report["cases"])
        self.assertEqual(0, report["mismatches"])

    def test_malformed_input_and_duplicate_keys_fail(self):
        with self.assertRaises(ValueError):
            json.loads('{"amount": 1, "amount": 2}', object_pairs_hook=unique_object)
        with self.assertRaises(ValueError):
            replay(b'{"profile":"unknown","cases":[]}')

    def test_mismatch_is_visible(self):
        path = Path(__file__).resolve().parents[1] / "clinic/corpus.json"
        corpus = json.loads(path.read_text())
        corpus["cases"][0]["expected"] = "DENY"
        report = replay(json.dumps(corpus).encode())
        self.assertEqual(1, report["mismatches"])
        self.assertEqual(1, report["bypass"])
