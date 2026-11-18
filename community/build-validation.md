# Inventory quality

How well does the rebuilt inventory represent one kilogram of the product it describes? A link identifies a supplier. The resulting inventory also depends on the amount purchased, the unit conversion, the choice of geography, any added or amended exchanges and the factors applied to emissions.

<!-- inventory quality measurements -->

## Measured inventory checks

Revision `2f7f8f3`. The review has evidence for 2 of 3 equally weighted checks.

| Check | Result | Observation |
|---|---|---|
| Required climate factors | Pass | 0 of 1 audited climate methods failed the required greenhouse-gas coverage check. |
| Reproduction of climate results | Fail | 2,163 of 2,450 climate scores fall within 5% of ADEME (88.3%). The acceptance target is 99%. |
| Evidence for an EF data-quality rating | Absent | Rated 0 of 3 own criteria. |

### Reference outputs in the source inventories

Of 17,966 source processes, 16,168 have at least one named product or waste-treatment output with a unit and an explicit, finite, nonzero quantity. 0 fail this check and 1,798 have insufficient evidence. Co-products are assessed together within their process. A parameter or formula requires its evaluated quantity before it can pass. The unit’s suitability and the amount’s accuracy require further evidence.

### What the AGRIBALYSE source documents

Across 17,966 source processes, 482 declare geography, 459 declare technology and 478 declare a time period. 2,491 describe collection methods and 383 include a representativeness statement.

These counts locate evidence for a reviewer. Assigning a product rating requires a documented sampling or estimation basis, independently assessed fit to the product, and the modelling basis of the included datasets. The current review record has no verified ratings for those inputs.

<!-- end inventory quality measurements -->

## Evidence from this build

| Question | Evidence to review |
|---|---|
| Did the import preserve the intended exchanges? | The [mapping record](../site/mapping.md) gives supplier-link counts, unit conversions and exchanges dropped. Review the identity, quantity and destination of changed exchanges. |
| Are the climate factors present? | The final inventory passed the build’s check for required core greenhouse-gas flows under its climate method. Other indicators and exclusions need their own coverage evidence. |
| Do the impact results reproduce ADEME’s values? | Of 2,450 climate scores with a non-zero reference after the near-zero rule, 2,163 (88.3%) fall within 5% of ADEME. The review target is 99%. The [Score stage](../site/build.md#run-step-5) records the test. |
| Does the stripped export reconstruct the same inventory? | The [Export stage](../site/build.md#run-step-6) records the checks on the stripped columns, the refilled matrices and the recalculated scores. |

## What an Inventory Quality Score would assess

A product-level Inventory Quality Score (IQS) would trace the reference unit through the final inventory. For each material input, it would examine the supplier’s technological and geographical fit, the amount and unit, the source of the evidence and its uncertainty. An amendment or an added dataset needs the same review, including the exchanges it changes downstream.

A defensible assessment identifies the exact inventory revision, the criterion, the observed value, the expected value and its source. Missing evidence stays visible. This build publishes measured checks. A product-level IQS assessment remains open.

## Account for every changed row

Report process, production, technosphere and biosphere counts at the source, imported and served stages. Each change needs a unique id, transition, exchange kind, signed row-count delta, reason and evidence link. The audit fails if the measured delta differs from the recorded changes. An equal total alone does not establish parity: compare stable exchange identities, amounts, units, compartments and declared supplier locations as well.

Keep declared supplier geography separately from resolved target geography. Stable dataset identifiers should determine links where available; a link resolved by identifier does not erase contradictory source metadata. Preserve raw lifecycle and aggregation signals rather than burying them in comments or assuming a sector folder captures retirement.

AGRIBALYSE already records pre/post link coverage and matrix drops through its dangling-edge auditor. Keep those reports, the curated mapping revisions, parameter overrides and export-parity results with each candidate. The BAFU issue counts are not AGRIBALYSE thresholds; reproduce AGRIBALYSE's own source and served exchange identities.

## Check characterization, not just linking

For each method, list the emitted flow keys, the flow keys required by its documented policy, the actual factors and explicit exclusions with evidence. Use complete identities (database/code, compartment, unit and region as appropriate), not substance name alone. **A supplied zero factor counts as characterized; an absent factor does not.** Never infer fossil versus non-fossil methane or copy an AR6 factor into EF 3.1 without the method source.

The required-flow list must come from the measured final inventory and a cited method policy. This tool checks the submitted audit; it cannot prove that a manually supplied inventory list is complete. Named exception evidence is still subject to review.

```sh
python3 scripts/build_checks.py path/to/build-audit.json
```

Start with [the synthetic audit example](../community/templates/build-audit.json). It demonstrates the format; its values and hashes are synthetic and certify no dataset build. A failed audit exits nonzero.

## Pin the inputs and the outputs

Keep source hashes and implementation revisions alongside actual SHA-256 hashes of output files. Hash the complete file bytes locally, for example with `shasum -a 256 path/to/output`.

The audit emits a **summary_sha256** over the dataset, scope, counts, changes, characterization audit, probes and applied packages. It ignores timestamps, serving locations and importer revisions, canonicalizes probe floats to 12 significant digits, and sorts unordered identity lists. That makes aggregate summaries comparable across rebuilds with negligible floating-point noise. It is a summary identity, **not a hash of the complete inventory** and not proof of numerical equivalence. The exact output-file hashes remain separate and may differ across platforms. Record score tolerances explicitly in the application test.

## Validate the contribution's actual claim

- **Import or mapping repair:** reproduce source identity and amounts; explain every added, removed, converted or redirected exchange; compare coverage and scores.
- **Representation/compression:** demonstrate lossless reconstruction within stated tolerances across the complete claimed columns, and score parity. A successful family round-trip alone is not an LCIA validation.
- **Disaggregation/reconstruction:** give the new inventory its own identity. Compare against the aggregated original; even a high mass-coverage ratio does not imply matching impacts.
- **Scenario or forecast:** hold scope fixed and record assumptions, uncertainty and held-out validation. A scenario is not automatically a correction of the provider's source dataset.

Publish only permitted aggregate evidence and metadata. Inventories, licensed background files and confidential partner evidence stay local. A passing technical check is not partner consensus; [the review workflow](workflow.md) records those decisions separately.
