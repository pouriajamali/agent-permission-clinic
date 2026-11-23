import json
from pathlib import Path
import unittest

from clinic.policy import Policy, decide, digest

CORPUS = Path(__file__).resolve().parents[1] / "fixtures" / "permission-pairs.json"


class ConformanceTests(unittest.TestCase):
    def test_independent_expected_corpus(self):
        corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
        allowed = denied = 0
        for case in corpus["cases"]:
            with self.subTest(case=case["id"]):
                actual = decide(Policy(**case.get("policy", {})), case["request"], now=case.get("now", 1000),
                                spent=case.get("spent", 0), reserved=case.get("reserved", 0))
                self.assertEqual(case["expected"], actual)
                allowed += case["expected"] == "ALLOW"
                denied += case["expected"] != "ALLOW"
        self.assertGreaterEqual(allowed, 5)
        self.assertGreaterEqual(denied, 10)

    def test_canonical_identity_binds_contents(self):
        request = json.loads(CORPUS.read_text())["cases"][0]["request"]
        self.assertEqual(digest(request), digest(dict(reversed(list(request.items())))))
        self.assertNotEqual(digest(request), digest(dict(request, amount=2)))

    def test_invalid_trusted_policy_rejected(self):
        for override in ({"quota": True}, {"revision": 0}, {"per_request": 11}, {"active": 1}, {"expires_at": -1}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                Policy(**override)


if __name__ == "__main__":
    unittest.main()
