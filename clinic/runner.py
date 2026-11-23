"""Replay an independently specified synthetic corpus; never invoke a wallet."""
import hashlib
from importlib.resources import files
import json

from .policy import PROFILE, Policy, decide


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def replay(raw=None):
    raw = raw if raw is not None else files("clinic").joinpath("corpus.json").read_bytes()
    corpus = json.loads(raw, object_pairs_hook=unique_object)
    if corpus.get("profile") != PROFILE:
        raise ValueError("unsupported corpus profile")
    cases = corpus["cases"]
    ids = [c["id"] for c in cases]
    if len(ids) != len(set(ids)) or not ids:
        raise ValueError("empty corpus or duplicate case identity")
    traces = []
    for case in cases:
        policy = Policy(**case.get("policy", {}))
        actual = decide(policy, case["request"], now=case.get("now", 1000),
                        spent=case.get("spent", 0), reserved=case.get("reserved", 0))
        traces.append(dict(case_id=case["id"], policy_revision=policy.revision,
                           expected=case["expected"], actual=actual, match=actual == case["expected"]))
    canonical = json.dumps(corpus, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return dict(profile=PROFILE, mode="policy-decision-only", corpus_sha256=hashlib.sha256(canonical).hexdigest(),
                cases=len(traces), mismatches=sum(not t["match"] for t in traces),
                bypass=sum(t["actual"] == "ALLOW" and t["expected"] != "ALLOW" for t in traces),
                false_rejection=sum(t["actual"] != "ALLOW" and t["expected"] == "ALLOW" for t in traces),
                limits=["Synthetic inputs only; not a wallet or vendor integration.",
                        "Decision replay is not storage enforcement, concurrency or crash evidence."], traces=traces)
