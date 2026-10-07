# Community contributions and consensus

This is the dataset's shared working space: canonical import → contributor layers → application and testing → reviewed consensus → recommendations to the dataset team.

Keep the canonical source and its import reproducible. Store each proposed correction, mapping, parameter scenario or process model as a separate contribution with a source release, pinned implementation revision, evidence and validation plan. Apply it in an isolated candidate build; retain the baseline and comparison outputs. A local experiment does not change the provider's official dataset.

Start with [the contribution template](templates/contribution.json), [the intake template](templates/intake.md), [application and testing](application-and-testing.md), and [the workflow](workflow.md). Evidence, proposals, runs and provider responses belong here together; this is more than a collection of feedback notes.

```sh
python3 scripts/community.py check
python3 scripts/community.py compare baseline-summary.json candidate-summary.json --out .local/comparisons/example.json
```

Comparisons require the same baseline identity and scope, matching metrics and finite values. They report deltas; they do not decide whether a change is scientifically correct. Acceptance requires actual validation evidence and named reviewer approvals.

No dataset-provider endorsement or new partner consensus is assumed. No packet is automatically sent. Public collaboration records must not expose confidential discussions or restricted source exports.
