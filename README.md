# Agent Permission Clinic

Replay authorized and denied agent tool calls against an explicit enforcement boundary, including open spending commitments.

Status: P0/P1/P2 have scoped evidence; P3 integration and P4 AI comparison are deferred with explicit gates. Storage reliability has a separate synthetic profile and tests. This is an educational conformance harness, not a wallet, a security audit, or production protection.

## Run offline

Requires Python 3.11 or newer and its standard library; no installation, wallet, account or network calls.

```sh
python -m clinic
python -m unittest discover -s tests -v
python tools/build.py
python -I dist/agent-permission-clinic.pyz
python -I dist/agent-permission-clinic.pyz --storage-demo local-results/demo
python tools/verify.py --output local-results/tests.json
```

The report lists each case's expected/actual reason and policy revision, plus bypass and false-rejection counts. Exit status 0 means all supplied expectations matched; 1 means a mismatch; 2 means invalid input. Use `--output report.json` or `--corpus custom.json`. Duplicate JSON keys are rejected. The corpus digest covers canonical sorted compact ASCII JSON, independent of file line endings. The initial corpus has 28 manually specified synthetic cases. The runner reports policy decisions; it does not move assets. Build produces an allowlisted deterministic zip application, runnable from a fresh directory without this source tree.

## One scenario

An operator gives `agent-A` permission `permit-1` to call `synthetic-transfer` for asset `SYN`, unit `credit`, destination `merchant-A`, before a fixed expiry. The permission has a total quota of 10 integer credits and a per-request maximum of 6. Two different requests for 6 must not both reserve the quota. A legitimate request for 4 followed by 6 must succeed. Calling a different destination, changing asset or unit, replaying an identity with changed contents, or executing after revoke must fail without a new effect.

The actor is an identifier supplied by a trusted local test driver. No authentication claim is made. The operator owns grant/revoke and the local database. An agent cannot legitimately edit the database or policy; an attacker who can do that is outside this profile.

## Threat model and enforcement

The untrusted input is the tool request. The trusted computing base is the local runner, its policy implementation, SQLite and the operator's control of the database and clock. No prompt or model response grants permission.

The enforcement point will be the storage transaction that checks the current permission, its revision, request identity and remaining quota, and inserts the reservation. Synthetic execution must recheck authorization and revision in a transaction that inserts a unique synthetic effect and consumes the reservation atomically. No external wallet is invoked. Checking policy and then independently sending a transaction would not satisfy this boundary.

| Threat | Required observation |
| --- | --- |
| Wrong amount/asset/unit/destination/actor/tool | Denied request creates no reservation or effect |
| Two workers race for the last quota | `spent + reserved <= quota` at committed storage state |
| Retry after lost response | Same canonical identity resolves the original outcome; changed payload conflicts |
| Revoke or expiry after reserve | Execute rechecks current authority; unconsumed hold can be safely released only for this synthetic profile |
| Old worker after policy revision | Revision mismatch prevents a new effect |
| Crash before/after reserve or effect commit | Durable state and restart preserve accounting and effect uniqueness |
| Forged service receipt | Request binding and claim type checked; an input boolean is never cryptographic verification |
| Overly restrictive implementation | Allowed boundary cases execute; false rejection is counted separately |

The operator owns recovery. Before commit SQLite rollback cancels local writes. After a synthetic effect commits it is not undone by revoke. Revoke blocks future execution and can release only unexecuted synthetic reservations. A real external adapter must retain uncertain holds until independent evidence proves no effect; this profile cannot establish that evidence for a network service. Cancellation, refund and rollback are distinct.

## Existing controls and the gap

Documentary review, 23 November 2026. The same 10-credit/two-6-request scenario is used as a comparison question, not as a claim that four products were executed.

| Baseline | Documented boundary | Same-scenario conclusion and remaining work |
| --- | --- | --- |
| [Coinbase Wallet MCP](https://docs.cdp.coinbase.com/ai-agents/coinbase-for-agents/wallet-mcp) | Shared budget reserves pending operations before signing; execution rechecks authority | Aggregate reservation already exists. No claim that Clinic invents it or exposes a bypass. Translate the scenario to a supported asset/window and test only with a separately scoped adapter. |
| [MetaMask period transfer enforcer](https://github.com/MetaMask/delegation-framework/blob/main/src/enforcers/ERC20PeriodTransferEnforcer.sol) | Transfer hook validates a token transfer and period allowance | Existing onchain allowance mechanism. Local open reservations are a different boundary; recipient/expiry/revoke require the complete delegation profile. No deployed contract test performed. |
| [Safe Guards](https://docs.safe.global/advanced/smart-account-guards) | Guard checks before and after a transaction; faulty guards can block execution | Scenario depends on guard, module and execution path. No guard implementation or Safe version was selected or tested. |
| [OPA](https://www.openpolicyagent.org/docs) | Policy decisions are separate from enforcement | A caller must make reservation and execution indivisible at its own effect boundary. No claim that a policy decision supplies atomic accounting. |

The scoped gap is a reproducible, secret-free local contract test with paired authorized/denied cases and visible storage/crash evidence. It is **not** a demonstrated missing vendor feature or security defect. Reuse existing wallet/policy controls through adapters; do not build a wallet engine. Existing private labs are not available or audited here, so no code is copied from them.

## Phase gates

P0 defines one actor/tool, authority owner, enforcement, rollback/revoke and this bounded gap. P1 adds independent expected results for allowed/denied pairs. P2 delivers an offline runner and fresh-install demo. P3 binds quota and service claims through versioned consumer contracts with CMP-02 (owned externally by G2) and CMP-06 (owned externally by G6). P4 compares model-assisted suggestions with a deterministic baseline using fixed budgets and held-out cases; a negative result or deferred experiment is recorded honestly. P5 tests process concurrency and crash/restart at the storage boundary. P6 requires an externally requested adapter, contract tests, policy migration and review. P0/P1/P2 are verified in their stated scope; P3/P4/P6 retain the gates in the integration document. P5 evidence is limited to the SQLite synthetic profile.

## Storage profile

`sqlite-delete-full-v1` has one permission per database, DELETE rollback journal, `synchronous=FULL`, explicit `BEGIN IMMEDIATE` and a bounded 15-second busy timeout. Reservation totals and the current permission are read and updated inside the writer transaction. A unique request identity and canonical payload digest prevent changed retries. The synthetic receipt and CONSUMED state commit in one transaction. Fences reject old workers; policy revisions are checked again at execution. Trusted operator methods own release, takeover, policy replacement and revoke. None authenticates a user. An external adapter cannot inherit this same-database atomicity.

The process tests synchronize actual spawned workers, exercise over-quota and legitimate exact-quota contention, duplicate identity, execute/revoke contention, stale workers and revision changes. Nine abrupt `os._exit(91)` crash points cover reservation, effect/consume, release and revoke around commit. Reopened databases are checked with independent SQL expectations and integrity checks. This tests process death on the selected filesystem; it does not simulate power loss, broken fsync, disk corruption or every schedule. The sequential `--storage-demo` is explanatory and is not counted as race evidence.

Storage semantics follow [SQLite transaction control](https://www.sqlite.org/lang_transaction.html) and [rollback-mode atomic commit assumptions](https://www.sqlite.org/atomiccommit.html). Changing to WAL, another database, an external wallet or another filesystem needs its own profile and evidence.

The first adapters are fakes. Shared contracts are fixtures until their owners publish compatible versions. A synthetic local stand-in is not a verified implementation of an upstream shared component. Integration does not require six running services. See [current integration and AI gates](docs/integration-gates.md); no unverified gate is implied complete.

## Publication boundary

Only newly authored code, docs and synthetic cases belong here. No employer code, account, private source snapshot, resume, raw ledger or secret is required. Live wallets, money, third-party attack testing, paid infrastructure and outreach are outside this harness. No AI advantage, production security, independent adoption or market demand is established.
