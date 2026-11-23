"""Replay an independently specified synthetic corpus; never invoke a wallet."""
import hashlib
from importlib.resources import files
import json

from .policy import PROFILE, Policy, decide, valid_text

REASONS = frozenset(("ALLOW", "SCHEMA", "AMOUNT", "REVOKED", "EXPIRED", "PERMISSION_ID", "ACTOR", "TOOL", "ASSET", "UNIT", "DESTINATION", "PER_REQUEST", "QUOTA"))


def invalid_constant(value):
    raise ValueError("non-JSON numeric constant: " + value)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def replay(raw=None):
    raw = raw if raw is not None else files("clinic").joinpath("corpus.json").read_bytes()
    if len(raw) > 1024 * 1024:
        raise ValueError("corpus exceeds 1 MiB")
    try:
        corpus = json.loads(raw, object_pairs_hook=unique_object, parse_constant=invalid_constant)
    except RecursionError as exc:
        raise ValueError("JSON nesting exceeds parser limit") from exc
    pending = [(corpus, 0)]
    while pending:
        value, depth = pending.pop()
        if depth > 16:
            raise ValueError("corpus nesting exceeds 16")
        if isinstance(value, dict):
            pending.extend((v, depth + 1) for v in value.values())
        elif isinstance(value, list):
            pending.extend((v, depth + 1) for v in value)
    if not isinstance(corpus, dict):
        raise ValueError("corpus root must be an object")
    if set(corpus) - {"profile", "provenance", "cases"}:
        raise ValueError("unknown corpus field")
    if corpus.get("profile") != PROFILE:
        raise ValueError("unsupported corpus profile")
    cases = corpus.get("cases")
    if not isinstance(cases, list) or not 0 < len(cases) <= 10000:
        raise ValueError("cases must be a nonempty array of at most 10000 objects")
    for case in cases:
        if not isinstance(case, dict) or not {"id", "request", "expected"} <= set(case):
            raise ValueError("case must contain id, request and expected")
        if set(case) - {"id", "request", "expected", "policy", "now", "spent", "reserved"}:
            raise ValueError("unknown case field")
        if not valid_text(case["id"]) or not isinstance(case["request"], dict):
            raise ValueError("invalid case identity/request")
        if not isinstance(case["expected"], str) or case["expected"] not in REASONS:
            raise ValueError("unknown expected reason")
        override = case.get("policy", {})
        if not isinstance(override, dict) or set(override) - set(Policy.__dataclass_fields__):
            raise ValueError("policy must be an object with supported fields")
    ids = [c["id"] for c in cases]
    if len(ids) != len(set(ids)):
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
