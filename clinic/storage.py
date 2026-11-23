"""Single-permission SQLite fake effect boundary, not a financial ledger.

The trusted operator owns the database, policy and clock. Only synthetic effects
inside this same SQLite transaction can be made atomic by this sample.
"""
from contextlib import contextmanager
from dataclasses import replace
import json
import os
from pathlib import Path
import sqlite3

from .policy import Policy, decide, digest, policy_dict, shape_reason, valid_text

STORAGE_PROFILE = "sqlite-delete-full-v1"


def crash(point, selected):
    # Explicit test-only injection: abrupt process death, not exception rollback.
    if point == selected:
        os._exit(91)


class Store:
    def __init__(self, path):
        self.path = str(path)

    @contextmanager
    def transaction(self):
        connection = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA synchronous=FULL")
            if connection.execute("PRAGMA journal_mode").fetchone()[0] != "delete":
                raise ValueError("storage profile requires DELETE journal")
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.execute("COMMIT")
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def initialize(self, policy=Policy()):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise ValueError("unsupported storage version")
            db.execute("CREATE TABLE IF NOT EXISTS policy (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL)")
            db.execute("""CREATE TABLE IF NOT EXISTS requests (
                request_id TEXT PRIMARY KEY, digest TEXT NOT NULL, payload TEXT NOT NULL,
                amount INTEGER NOT NULL CHECK(amount>0), revision INTEGER NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('HELD','CONSUMED','RELEASED')),
                worker TEXT NOT NULL, fence INTEGER NOT NULL CHECK(fence>0))""")
            db.execute("""CREATE TABLE IF NOT EXISTS effects (
                request_id TEXT PRIMARY KEY REFERENCES requests(request_id), receipt TEXT NOT NULL)""")
            encoded = json.dumps(policy_dict(policy), sort_keys=True)
            existing = db.execute("SELECT body FROM policy WHERE id=1").fetchone()
            if existing and existing["body"] != encoded:
                raise ValueError("existing policy differs; initialize cannot overwrite grants")
            db.execute("INSERT OR IGNORE INTO policy VALUES (1, ?)", (encoded,))
            db.execute("PRAGMA user_version=1")

    @staticmethod
    def _policy(db):
        if db.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise ValueError("unsupported storage version")
        return Policy(**json.loads(db.execute("SELECT body FROM policy WHERE id=1").fetchone()[0]))

    @staticmethod
    def _totals(db):
        totals = dict(db.execute("SELECT state, COALESCE(SUM(amount),0) FROM requests GROUP BY state"))
        return dict(spent=totals.get("CONSUMED", 0), reserved=totals.get("HELD", 0))

    def reserve(self, request, *, now, worker="worker-A", crash_at=None):
        reason = shape_reason(request)
        if reason:
            return dict(reason=reason)
        if not valid_text(worker):
            return dict(reason="WORKER")
        fingerprint = digest(request)
        result = None
        with self.transaction() as db:
            policy = self._policy(db)
            prior = db.execute("SELECT * FROM requests WHERE request_id=?", (request["request_id"],)).fetchone()
            if prior:
                # Lookup resolves an existing outcome; it does not grant fresh authority.
                result = dict(reason="CONFLICT") if prior["digest"] != fingerprint else dict(reason="REPLAY", state=prior["state"])
            else:
                totals = self._totals(db)
                reason = decide(policy, request, now=now, **totals)
                result = dict(reason=reason)
                if reason == "ALLOW":
                    db.execute("INSERT INTO requests VALUES (?,?,?,?,?,'HELD',?,1)",
                               (request["request_id"], fingerprint, json.dumps(request, sort_keys=True),
                                request["amount"], policy.revision, worker))
                    result.update(state="HELD", fence=1, worker=worker)
                    crash("reserve-before-commit", crash_at)
        crash("reserve-after-commit", crash_at)
        return result

    def take_over(self, request_id, *, worker):
        """Trusted local supervisor rotates a fence; not an agent-facing API."""
        if not valid_text(worker):
            raise ValueError("invalid worker")
        with self.transaction() as db:
            self._policy(db)
            row = db.execute("SELECT * FROM requests WHERE request_id=?", (request_id,)).fetchone()
            if not row or row["state"] != "HELD":
                return dict(reason="NOT_HELD")
            fence = row["fence"] + 1
            db.execute("UPDATE requests SET worker=?,fence=? WHERE request_id=?", (worker, fence, request_id))
            return dict(reason="TAKEN_OVER", fence=fence, worker=worker)

    def execute(self, request, *, now, worker="worker-A", fence=1, crash_at=None):
        reason = shape_reason(request)
        if reason:
            return dict(reason=reason)
        with self.transaction() as db:
            policy = self._policy(db)
            row = db.execute("SELECT * FROM requests WHERE request_id=?", (request["request_id"],)).fetchone()
            if not row:
                return dict(reason="NOT_RESERVED")
            if row["digest"] != digest(request):
                return dict(reason="CONFLICT")
            if row["state"] == "CONSUMED":
                receipt = db.execute("SELECT receipt FROM effects WHERE request_id=?", (request["request_id"],)).fetchone()
                return dict(reason="REPLAY", receipt=json.loads(receipt[0]))
            if row["state"] != "HELD":
                return dict(reason="RELEASED")
            if type(fence) is not int or fence != row["fence"] or worker != row["worker"]:
                return dict(reason="STALE_WORKER")
            if row["revision"] != policy.revision:
                return dict(reason="POLICY_CHANGED")
            totals = self._totals(db)
            reason = decide(policy, request, now=now, spent=totals["spent"], reserved=totals["reserved"] - row["amount"])
            if reason != "ALLOW":
                return dict(reason=reason)
            receipt = dict(profile=STORAGE_PROFILE, request_id=request["request_id"], intent_digest=row["digest"],
                           asset=request["asset"], unit=request["unit"], amount=request["amount"],
                           destination=request["destination"], claim="synthetic-local-effect-only")
            db.execute("INSERT INTO effects VALUES (?,?)", (request["request_id"], json.dumps(receipt, sort_keys=True)))
            crash("effect-before-consume", crash_at)
            db.execute("UPDATE requests SET state='CONSUMED' WHERE request_id=?", (request["request_id"],))
            crash("consume-before-commit", crash_at)
        crash("consume-after-commit", crash_at)
        return dict(reason="CONSUMED", receipt=receipt)

    def release(self, request_id, *, crash_at=None):
        """Trusted operator: safe only because no external effect exists in this profile."""
        with self.transaction() as db:
            self._policy(db)
            changed = db.execute("UPDATE requests SET state='RELEASED' WHERE request_id=? AND state='HELD'", (request_id,)).rowcount
            crash("release-before-commit", crash_at)
        crash("release-after-commit", crash_at)
        return dict(reason="RELEASED" if changed else "NO_CHANGE")

    def revoke(self, *, crash_at=None):
        with self.transaction() as db:
            policy = self._policy(db)
            revoked = replace(policy, active=False, revision=policy.revision + 1)
            db.execute("UPDATE policy SET body=? WHERE id=1", (json.dumps(policy_dict(revoked), sort_keys=True),))
            db.execute("UPDATE requests SET state='RELEASED' WHERE state='HELD'")
            crash("revoke-before-commit", crash_at)
        crash("revoke-after-commit", crash_at)
        return dict(reason="REVOKED")

    def replace_policy(self, replacement, *, expected_revision):
        """Trusted operator only; explicit revision and unchanged accounting scope."""
        with self.transaction() as db:
            current = self._policy(db)
            if type(expected_revision) is not int or current.revision != expected_revision or replacement.revision != current.revision + 1:
                raise ValueError("policy revision conflict")
            if any(getattr(current, key) != getattr(replacement, key) for key in ("permission_id", "asset", "unit")):
                raise ValueError("accounting scope migration requires a new database")
            totals = self._totals(db)
            if totals["spent"] + totals["reserved"] > replacement.quota:
                raise ValueError("new quota would violate existing commitments")
            db.execute("UPDATE policy SET body=? WHERE id=1", (json.dumps(policy_dict(replacement), sort_keys=True),))


    def snapshot(self):
        with self.transaction() as db:
            policy = self._policy(db)
            totals = self._totals(db)
            requests = [dict(row) for row in db.execute("SELECT request_id,amount,state,worker,fence,revision FROM requests ORDER BY request_id")]
            effects = [json.loads(row[0]) for row in db.execute("SELECT receipt FROM effects ORDER BY request_id")]
            if totals["spent"] + totals["reserved"] > policy.quota:
                raise AssertionError("quota invariant violated")
            if len(effects) != sum(r["state"] == "CONSUMED" for r in requests):
                raise AssertionError("effect/consume invariant violated")
            return dict(profile=STORAGE_PROFILE, policy=policy_dict(policy), **totals, requests=requests, effects=effects,
                        sqlite_version=sqlite3.sqlite_version, integrity=db.execute("PRAGMA integrity_check").fetchone()[0])
