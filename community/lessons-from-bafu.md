# Lessons from the BAFU/UVEK workspace

These are engineering lessons from lci-bafu-catalog and the BAFU/UVEK workspace, and how each applies to the import of AGRIBALYSE. They are not findings about ADEME's data: a finding needs a named release, an observation and a measurement on ADEME's files that a second person can repeat, and has its own record. A problem of the import or of a method belongs to the code that introduced it.

## Current review

| Topic | Evidence | Application here | Status |
|---|---|---|---|
| Silent losses between source and served exchanges | [BAFU importer parity #2](https://github.com/sentier-dev/sentier-bafu/issues/2) | Named row-delta reconciliation; retain existing drop and dangling-edge reports | Shared audit tool implemented; licensed baseline reconciliation not run |
| Linked greenhouse gases with missing CFs | [Method derivation #5](https://github.com/sentier-dev/sentier-bafu/issues/5) | Audit the final scoring biosphere; distinguish missing factors from explicit zeros | `scripts/build_checks.py` checks a submitted build audit; a check inside the adapter's emit stage continues on a branch of its own; a pull request for it follows this one |
| Identity changes across rebuilds | [Build identity #5](https://github.com/sentier-dev/sentier-bafu/issues/5) | Keep exact output hashes and a portable aggregate-summary identity | Shared summary tool implemented; not a full inventory fingerprint |
| Aggregated inventories versus reconstructions | [Aggregated datasets #3](https://github.com/sentier-dev/sentier-bafu/issues/3) | Separate candidate identity, scope and score comparison | Review requirement; no equivalence inferred |
| Retired processes selected unknowingly | [Maintenance signals #4](https://github.com/sentier-dev/sentier-bafu/issues/4) | Preserve AGRIBALYSE lifecycle signals when supplied; examine stale mapping anchors | Requires AGRIBALYSE-specific evidence; BAFU prefixes are not copied |
| Artifact-specific redistribution terms | [Redistribution discussion #1](https://github.com/sentier-dev/sentier-bafu/issues/1) | Distinguish public results, foreground evidence and licensed background exports | Documented; no new distribution agreement assumed |

No defect of an AGRIBALYSE value and no recommendation to ADEME is asserted by this page. No new licensed baseline has been reproduced in this documentation work. The BAFU strawberry, refrigerant and cement observations remain BAFU findings; they may affect a BAFU-background candidate but do not describe canonical AGRIBALYSE.

## Add a finding

[Open a finding](https://github.com/sentier-dev/sentier-agribalyse/issues/new?template=agribalyse-data-finding.yml) with the release, what it concerns, what you measured and how. Record whether the observation comes from source files, an imported representation or a served result. Invite independent reproduction; keep unresolved interpretations explicit.

If a contribution addresses it, link its record in `contributions/` and its [validation](build-validation.md). A workaround does not close the provider question. Reviewed recommendations and actual ADEME responses belong in [the recommendation tracker](recommendations/).
