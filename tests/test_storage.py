from dataclasses import replace
from contextlib import closing
import multiprocessing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from clinic.policy import Policy
from clinic.storage import Store

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / ".test-tmp"
REQUEST = dict(request_id="request-A", permission_id="permit-1", actor="agent-A", tool="synthetic-transfer",
               asset="SYN", unit="credit", destination="merchant-A", amount=6)


def worker(path, operation, request, barrier, queue, crash_at=None):
    store = Store(path)
    try:
        if barrier:
            barrier.wait(timeout=20)
        if operation == "reserve":
            result = store.reserve(request, now=1000, crash_at=crash_at)
        elif operation == "execute":
            result = store.execute(request, now=1000, crash_at=crash_at)
        elif operation == "release":
            result = store.release(request["request_id"], crash_at=crash_at)
        else:
            result = store.revoke(crash_at=crash_at)
        if queue:
            queue.put(result)
    except BaseException as exc:
        if queue:
            queue.put(dict(error=repr(exc)))
        else:
            raise


class StorageTests(unittest.TestCase):
    def setUp(self):
        TMP.mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=TMP)
        self.addCleanup(self.directory.cleanup)
        self.path = str(Path(self.directory.name) / "case.sqlite3")
        self.store = Store(self.path)
        self.store.initialize()
        self.ctx = multiprocessing.get_context("spawn")

    def run_workers(self, operations, requests):
        barrier = self.ctx.Barrier(len(operations))
        queue = self.ctx.Queue()
        processes = [self.ctx.Process(target=worker, args=(self.path, op, req, barrier, queue)) for op, req in zip(operations, requests)]
        for process in processes:
            process.start()
        results = []
        try:
            for _ in processes:
                results.append(queue.get(timeout=40))
        finally:
            for process in processes:
                process.join(timeout=5)
                if process.is_alive():
                    process.terminate()
                    process.join()
                    self.fail("bounded worker did not finish")
            queue.close()
            queue.join_thread()
        self.assertTrue(all(p.exitcode == 0 for p in processes))
        self.assertTrue(all("error" not in r for r in results), results)
        return results

    def raw_oracle(self, spent, reserved, effects):
        # Independent SQL reads, not Store.snapshot's internal invariant checks.
        with closing(sqlite3.connect(self.path)) as db:
            rows = db.execute("SELECT state,amount FROM requests").fetchall()
            self.assertEqual(spent, sum(a for s, a in rows if s == "CONSUMED"))
            self.assertEqual(reserved, sum(a for s, a in rows if s == "HELD"))
            self.assertEqual(effects, db.execute("SELECT COUNT(*) FROM effects").fetchone()[0])
            self.assertEqual("ok", db.execute("PRAGMA integrity_check").fetchone()[0])
        self.assertLessEqual(spent + reserved, 10)

    def test_process_race_rejects_aggregate_overcommit(self):
        results = self.run_workers(["reserve"] * 8, [dict(REQUEST, request_id=f"race-{i}") for i in range(8)])
        self.assertEqual(1, sum(r["reason"] == "ALLOW" for r in results))
        self.assertEqual(7, sum(r["reason"] == "QUOTA" for r in results))
        self.raw_oracle(0, 6, 0)

    def test_concurrent_boundary_is_not_falsely_rejected(self):
        requests = [dict(REQUEST, request_id=f"exact-{i}", amount=2) for i in range(5)]
        self.assertTrue(all(r["reason"] == "ALLOW" for r in self.run_workers(["reserve"] * 5, requests)))
        self.raw_oracle(0, 10, 0)
        self.assertTrue(all(r["reason"] == "CONSUMED" for r in self.run_workers(["execute"] * 5, requests)))
        self.raw_oracle(10, 0, 5)

    def test_duplicate_workers_commit_one_effect(self):
        results = self.run_workers(["reserve"] * 8, [REQUEST] * 8)
        self.assertEqual(1, sum(r["reason"] == "ALLOW" for r in results))
        self.assertEqual(7, sum(r["reason"] == "REPLAY" for r in results))
        results = self.run_workers(["execute"] * 8, [REQUEST] * 8)
        self.assertEqual(1, sum(r["reason"] == "CONSUMED" for r in results))
        self.assertEqual(7, sum(r["reason"] == "REPLAY" for r in results))
        self.raw_oracle(6, 0, 1)

    def test_conflict_never_reuses_identity_for_new_effect(self):
        self.store.reserve(REQUEST, now=1000)
        for operation in (self.store.reserve, self.store.execute):
            self.assertEqual("CONFLICT", operation(dict(REQUEST, amount=4), now=1000)["reason"])
        self.raw_oracle(0, 6, 0)

    def test_stale_worker_is_fenced_at_effect_transaction(self):
        self.store.reserve(REQUEST, now=1000)
        takeover = self.store.take_over(REQUEST["request_id"], worker="worker-B")
        self.assertEqual(2, takeover["fence"])
        self.assertEqual("STALE_WORKER", self.store.execute(REQUEST, now=1000)["reason"])
        self.assertEqual("STALE_WORKER", self.store.execute(REQUEST, now=1000, worker="worker-B", fence=True)["reason"])
        self.assertEqual("CONSUMED", self.store.execute(REQUEST, now=1000, worker="worker-B", fence=2)["reason"])
        self.raw_oracle(6, 0, 1)

    def test_revoke_and_execute_serialize_without_undoing_effects(self):
        self.store.reserve(REQUEST, now=1000)
        results = self.run_workers(["execute", "revoke"], [REQUEST] * 2)
        snapshot = self.store.snapshot()
        effects = len(snapshot["effects"])
        self.assertIn(effects, (0, 1))
        self.assertFalse(snapshot["policy"]["active"])
        self.assertEqual(0, snapshot["reserved"])
        self.raw_oracle(6 * effects, 0, effects)
        self.assertEqual("REVOKED", self.store.reserve(dict(REQUEST, request_id="after-revoke"), now=1000)["reason"])
        self.assertTrue(any(r["reason"] == "REVOKED" for r in results))

    def test_expiry_rechecks_and_release_does_not_resurrect_identity(self):
        self.store.reserve(REQUEST, now=1999)
        self.assertEqual("EXPIRED", self.store.execute(REQUEST, now=2000)["reason"])
        self.raw_oracle(0, 6, 0)
        self.store.release(REQUEST["request_id"])
        self.assertEqual(dict(reason="REPLAY", state="RELEASED"), self.store.reserve(REQUEST, now=1000))
        self.assertEqual("RELEASED", self.store.execute(REQUEST, now=1000)["reason"])
        self.raw_oracle(0, 0, 0)

    def test_policy_revision_and_scope_migration_fail_closed(self):
        self.store.reserve(REQUEST, now=1000)
        with self.assertRaises(ValueError):
            self.store.replace_policy(replace(Policy(), quota=5, per_request=5, revision=2), expected_revision=1)
        with self.assertRaises(ValueError):
            self.store.replace_policy(replace(Policy(), asset="OTHER", revision=2), expected_revision=1)
        self.store.replace_policy(replace(Policy(), destination="merchant-B", revision=2), expected_revision=1)
        self.assertEqual("POLICY_CHANGED", self.store.execute(REQUEST, now=1000)["reason"])
        with self.assertRaises(ValueError):
            self.store.replace_policy(replace(Policy(), revision=3), expected_revision=1)
        self.raw_oracle(0, 6, 0)

    def test_denials_have_no_effect_and_execution_needs_reservation(self):
        self.assertEqual("NOT_RESERVED", self.store.execute(REQUEST, now=1000)["reason"])
        for field, value in (("amount", 7), ("destination", "attacker"), ("actor", "other"), ("tool", "other"), ("unit", "other"), ("asset", "other")):
            result = self.store.reserve(dict(REQUEST, **{field: value}), now=1000)
            self.assertNotEqual("ALLOW", result["reason"])
        self.raw_oracle(0, 0, 0)

    def test_crash_restart_matrix_uses_abrupt_process_exit(self):
        cases = [
            ("reserve", "reserve-before-commit", False, 0, 0, 0, True),
            ("reserve", "reserve-after-commit", False, 0, 6, 0, True),
            ("execute", "effect-before-consume", True, 0, 6, 0, True),
            ("execute", "consume-before-commit", True, 0, 6, 0, True),
            ("execute", "consume-after-commit", True, 6, 0, 1, True),
            ("release", "release-before-commit", True, 0, 6, 0, True),
            ("release", "release-after-commit", True, 0, 0, 0, True),
            ("revoke", "revoke-before-commit", True, 0, 6, 0, True),
            ("revoke", "revoke-after-commit", True, 0, 0, 0, False),
        ]
        for index, (op, point, reserve_first, spent, held, effects, active) in enumerate(cases):
            with self.subTest(point=point):
                self.path = str(Path(self.directory.name) / f"crash-{index}.sqlite3")
                store = Store(self.path)
                store.initialize()
                if reserve_first:
                    store.reserve(REQUEST, now=1000)
                process = self.ctx.Process(target=worker, args=(self.path, op, REQUEST, None, None, point))
                process.start()
                process.join(timeout=25)
                if process.is_alive():
                    process.terminate()
                    process.join()
                    self.fail("crash worker did not exit")
                self.assertEqual(91, process.exitcode)
                self.raw_oracle(spent, held, effects)
                self.assertEqual(active, Store(self.path).snapshot()["policy"]["active"])
                if op == "execute":
                    retry = Store(self.path).execute(REQUEST, now=1000)
                    self.assertEqual("REPLAY" if effects else "CONSUMED", retry["reason"])
                    self.raw_oracle(6, 0, 1)
