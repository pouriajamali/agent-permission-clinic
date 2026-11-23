import json
from pathlib import Path
import subprocess
import sys
import tempfile
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
        corpus["cases"][0]["expected"] = "ASSET"
        report = replay(json.dumps(corpus).encode())
        self.assertEqual(1, report["mismatches"])
        self.assertEqual(1, report["bypass"])

    def test_cli_and_zipapp_reject_malformed_corpus_without_traceback(self):
        root = Path(__file__).resolve().parents[1]
        scratch = root / ".test-tmp"
        scratch.mkdir(exist_ok=True)
        artifact = build()
        malformed = [[], None, 1, True, "text", {"profile": "clinic-synthetic-v1", "cases": None},
                     {"profile": "clinic-synthetic-v1", "cases": [None]},
                     {"profile": "clinic-synthetic-v1", "cases": [{"id": "incomplete"}]},
                     {"profile": "clinic-synthetic-v1", "cases": [{"id": [], "request": {}, "expected": "ALLOW"}]},
                     {"profile": "clinic-synthetic-v1", "cases": [{"id": "x", "request": {}, "expected": [], "policy": []}]}]
        malformed += [{"profile": "clinic-synthetic-v1", "cases": [{"id": "x", "request": {}, "expected": "SCHEMA", "policy": []}]}]
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            path = Path(directory) / "invalid.json"
            for value in malformed:
                path.write_text(json.dumps(value), encoding="utf-8")
                for command in ([sys.executable, "-m", "clinic"], [sys.executable, "-I", str(artifact)]):
                    with self.subTest(value=value, command=command):
                        result = subprocess.run([*command, "--corpus", str(path)], capture_output=True, text=True)
                        self.assertEqual(2, result.returncode, result.stderr)
                        self.assertIn("clinic:", result.stderr)
                        self.assertNotIn("Traceback", result.stderr)

    def test_packaged_storage_demo_matches_explicit_end_state(self):
        root = Path(__file__).resolve().parents[1]
        artifact = build()
        result = subprocess.run([sys.executable, "-I", str(artifact), "--storage-demo", str(root / ".test-tmp")],
                                capture_output=True, text=True, cwd=artifact.parents[2])
        self.assertEqual(0, result.returncode, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(0, report["mismatches"])
        self.assertEqual((10, 0, 2), (report["snapshot"]["spent"], report["snapshot"]["reserved"], len(report["snapshot"]["effects"])))
