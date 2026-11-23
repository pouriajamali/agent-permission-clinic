# Consumer integration gates

G3 owns the permission harness. It consumes CMP-02 from G2 and CMP-06 from G6; it does not own or redefine either shared component. Offline fixtures are sufficient to develop this harness, but do not establish upstream compatibility.

## P3 decision: deferred for upstream contracts

Snapshot reviewed on 23 November 2026:

* G2's `docs/contract-v1.md` describes `traceVersion=1.0`, `lifi-status-observation-v1`. Intent identity is canonical SHA-256 and asset amounts are decimal atomic strings with explicit decimals. It explicitly reports `ledger=notIntegrated`. There is no published reservation/recovery contract here to pin and consume as CMP-02. Do not reinterpret a read-only trace as a quota ledger.
* G6's profile at commit `5807a441e12632df9d4de995ed597d0d6509f893` is `vc-jws-eddsa-receipt/0.1.0`, receipt `service-receipt/0.1.0`, with `jose=6.2.18`. It distinguishes signature, credential, binding and scope. P3 consumer adapters are still a separate gate. An authentic issuer statement does not prove computation quality, execution or settlement. G3 has not run that verifier and does not claim it has.
* G3 uses integer `SYN/credit`. The G6 example charge is `USD/microusd`; these are not interchangeable. G2 atomic strings and decimals cannot be silently converted to a floating point amount or to G3's synthetic quota unit.

The local G3 SQLite sample is a fake effect boundary for testing permission invariants, not a general-purpose replacement for the G2 ledger. No code or fixture was copied from sibling repositories; these observations inform consumer requirements only.

## Conditions to resume P3

1. Pin a G2-owned reservation contract/artifact hash and database profile: identity, canonical digest, asset/unit/precision, quota scope, HELD/CONSUMED/RELEASED or explicit native equivalents, idempotency conflict and unknown outcomes.
2. Pin a G6-owned verifier and complete expected context: request ID, input/output digest, model/code version, quote, exact charge asset/unit/amount, domain and nonce, issuer/key policy and validity/replay behavior. Verify wrong-request and unsupported-claim cases with the actual verifier, not a supplied true/false input.
3. Bind the permission ID separately from request identity; require the exact intent contents checked by the reservation contract. Match receipt charge to the agreed unit and reserved amount. Refuse unknown versions, units, verification types and unsupported claims without converting absence to success or zero.
4. Run independent consumer tests for canonical conflict, duplicate/restart, spent plus reserved across workers, wrong request/model/input/output/charge/domain and missing/failed service. Preserve payment, service, signature and quality as independent outcomes.

An unavailable contract is a dependency gate, not revoked implementation permission. Independent G3 storage/concurrency tests can proceed while these integrations remain deferred.

## P4 decision: experiment deferred

No separately executable model, pinned model revision, fixed inference budget or independently labelled held-out scenario set has been selected for a fair experiment. Coding-assistant suggestions and the fixtures authored during implementation are not such an experiment. AI advantage is unmeasured. The deterministic checker remains the authority and request fields such as `authorization=model-says-yes` are rejected by the corpus.

Resume by freezing task, holdout and deterministic baseline before model generation, recording all suggestions including invalid/duplicate ones, validating with an independent oracle, and measuring bypass, false rejection, new valid coverage, elapsed time and token/cost budget. A negative result is acceptable. Model output must never update grants, quota or trusted expected results.

## P6 gate

An adapter for an externally requested tool requires demonstrated demand and a reviewer. No independent consumer request or reviewer evidence exists yet. Do not invent one or connect a live wallet to finish a checklist. Keep contribution instructions and the existing fake profile reproducible; maintain the full P0-P6 roadmap.
