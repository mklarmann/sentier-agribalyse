# Build runs

## Full-source verification

The same adapter revision, ecoinvent background and climate acceptance target were used for both inputs. The additional run read ADEME’s full licensed SimaPro export locally. [Compare the results by source](build.md).

<!-- full source checks -->

Run started **2026-11-18 23:31:27 CET** on revision `2f7f8f3`. The local Brightway export passed its sampled score check. The extracts below come from the climate and Brightway runs.

<pre tabindex="0"><code>    ok   the build read the full export
    ok   climate change within 5% of ADEME for at least 99% of products
  parity check: PASS (57 scores, max rel error 1.24e-15)</code></pre>

<!-- end full source checks -->

The shareable-package command stopped at its licence check when it found copied ecoinvent blocks in the full-source inventory. For the distributable input, the recorded run completed the export and recovered the original matrices and scores after refilling the package. [See its Export stage](build.md#run-step-6).

To reproduce the full-source run on a licensed machine, place ADEME’s full AGRIBALYSE 3.2 export at `source/AGB32_final.CSV` before running the import. The run report identifies the selected source. [Input selection](../IMPORT.md#the-agribalyse-csv).

## Run from the distributable source

The [six-stage terminal replay](build.md#the-last-run) follows the local build of AGRIBALYSE 3.2 on ecoinvent 3.9.1. Its stage timings, command outcomes and acceptance checks come from that execution.

- [Read the comparison with ADEME’s climate results](build.md#run-step-5).
- [Inspect the stripped-package and refill checks](build.md#run-step-6).
- [Read the public run record as JSON](api/v1/last-run.json).

The review run includes the changes proposed for [stripping and refilling the export](https://github.com/sentier-dev/sentier-agribalyse/pull/11), [the community workspace and data safeguards](https://github.com/sentier-dev/sentier-agribalyse/pull/12), and [the software licence](https://github.com/sentier-dev/sentier-agribalyse/pull/14). Each proposal links to its current upstream status.

## Automated checks

GitHub checks the checksum and process count of the distributable AGRIBALYSE export. The site keeps the licensed run above available when a new automated check finishes. [View the history of automated import checks](https://github.com/mklarmann/sentier-agribalyse/actions/workflows/import-run.yml).
