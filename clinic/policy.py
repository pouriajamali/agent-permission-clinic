"""Deterministic policy; authorization inputs come from a trusted local driver."""

from dataclasses import asdict, dataclass
import hashlib
import json

PROFILE = "clinic-synthetic-v1"
MAX_INTEGER = 2**63 - 1
FIELDS = frozenset(("request_id", "permission_id", "actor", "tool", "asset", "unit", "destination", "amount"))


@dataclass(frozen=True)
class Policy:
    permission_id: str = "permit-1"
    actor: str = "agent-A"
    tool: str = "synthetic-transfer"
    asset: str = "SYN"
    unit: str = "credit"
    destination: str = "merchant-A"
    per_request: int = 6
    quota: int = 10
    expires_at: int = 2000
    revision: int = 1
    active: bool = True

    def __post_init__(self):
        for name in ("per_request", "quota", "expires_at", "revision"):
            value = getattr(self, name)
            if type(value) is not int or not 0 < value <= MAX_INTEGER:
                raise ValueError("invalid policy integer: " + name)
        if self.per_request > self.quota or type(self.active) is not bool:
            raise ValueError("invalid policy limits/active")
        for name in ("permission_id", "actor", "tool", "asset", "unit", "destination"):
            if not valid_text(getattr(self, name)):
                raise ValueError("invalid policy identifier: " + name)


def valid_text(value):
    return isinstance(value, str) and 0 < len(value) <= 128 and all(32 < ord(c) < 127 for c in value)


def shape_reason(request):
    if not isinstance(request, dict) or set(request) != FIELDS:
        return "SCHEMA"
    if any(not valid_text(request[name]) for name in FIELDS - {"amount"}):
        return "SCHEMA"
    if type(request["amount"]) is not int or not 0 < request["amount"] <= MAX_INTEGER:
        return "AMOUNT"
    return None


def digest(request):
    reason = shape_reason(request)
    if reason:
        raise ValueError(reason)
    return hashlib.sha256(json.dumps(request, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def decide(policy, request, *, now, spent=0, reserved=0):
    """Return a reason; ALLOW alone never creates an effect or reserves quota."""
    if type(now) is not int or now < 0 or any(type(v) is not int or v < 0 for v in (spent, reserved)):
        raise ValueError("trusted clock/accounting must be nonnegative integers")
    reason = shape_reason(request)
    if reason:
        return reason
    if not policy.active:
        return "REVOKED"
    if now >= policy.expires_at:
        return "EXPIRED"
    for name in ("permission_id", "actor", "tool", "asset", "unit", "destination"):
        if request[name] != getattr(policy, name):
            return name.upper()
    if request["amount"] > policy.per_request:
        return "PER_REQUEST"
    if spent + reserved + request["amount"] > policy.quota:
        return "QUOTA"
    return "ALLOW"


def policy_dict(policy):
    return asdict(policy)
