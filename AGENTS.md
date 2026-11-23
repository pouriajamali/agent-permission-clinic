# Project execution policy

The owner's instruction of 23 November 2026 forbids all new CI and hosted workflow execution. Do not dispatch or rerun GitHub Actions, and do not cause CI through push, pull request, merge, schedule or release. Local builds and tests remain allowed. Historical CI records are dated evidence only.

The prior conformance workflow is preserved under `docs/disabled-workflows/conformance.yml.disabled`. It is outside the active `.github/workflows` directory. Do not restore, enable or add an active workflow without a new explicit owner instruction. Before any publication inspect the current remote branches/tree and ensure no workflow can trigger; otherwise retain changes locally. Do not alter shared or frozen baseline CI.

Send exactly one consolidated message to the technical manager at the end of each phase. Do not send acknowledgments, mid-phase notices, repeated phase reports or correction notices for an already reported phase. Update local evidence for an already reported phase; include necessary corrections in the next phase's single report. Applying this policy is not a new phase and sends no manager message. Preserve historical reports and observations.

Keep the synthetic harness offline, preserve the distinction between policy decision and enforcement, and retain the documented dependency and scientific gates. Never publish private handoff material, employer code/data, credentials or real wallet inputs.
