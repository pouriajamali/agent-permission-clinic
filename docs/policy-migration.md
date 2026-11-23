# Policy and storage changes

Policy profile `clinic-synthetic-v1` and storage schema `user_version=1` are local contracts. Unknown storage versions are refused. Opening a database through `initialize` cannot overwrite an existing grant. The trusted operator must explicitly replace policy with the expected old revision and exactly the next revision. Changing asset, unit or permission identity requires a separate database/migration design; no conversion is inferred.

Example: with six credits held under revision 1, replace the destination with `merchant-B` under revision 2 using `replace_policy(replace(Policy(), destination='merchant-B', revision=2), expected_revision=1)`. The old worker receives `POLICY_CHANGED` and creates no effect. The operator can release the unexecuted synthetic hold; a new request with a new identity may then be admitted under the new destination. Lowering quota below existing spent plus reserved is rejected. A stale expected revision is rejected. Reinitializing or replaying a RELEASED identity never grants new authority.

Revocation blocks new admissions and releases only unconsumed local synthetic holds. A consumed receipt remains available for lookup and does not imply that execution was newly authorized after revoke. Returning an existing outcome and authorizing a new effect are distinct.

Before changing schema, policy semantics, transaction mode or adapter behavior, add an old/new example, negative contract tests and independent expected outcomes. Review affected consumers and record the dependency versions. Do not rewrite a database in place merely to pass a demo. The fake profile has no network-side uncertain outcome; external adapters must retain uncertain reservations and define independent recovery evidence before release.
