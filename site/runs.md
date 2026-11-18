# Build runs

## Licensed review build · 18 November 2026

The [six-stage terminal replay](build.md#the-last-run) follows the local build of AGRIBALYSE 3.2 on ecoinvent 3.9.1. Its stage timings, command outcomes and acceptance checks come from that execution.

- [Read the comparison with ADEME’s climate results](build.md#run-step-5).
- [Inspect the stripped-package and refill checks](build.md#run-step-6).
- [Read the public run record as JSON](api/v1/last-run.json).

The review run includes the changes proposed for [stripping and refilling the export](https://github.com/sentier-dev/sentier-agribalyse/pull/11), [the community workspace and data safeguards](https://github.com/sentier-dev/sentier-agribalyse/pull/12), and [the software licence](https://github.com/sentier-dev/sentier-agribalyse/pull/14). Each proposal links to its current upstream status.

## Automated checks

GitHub checks the checksum and process count of the distributable AGRIBALYSE export. The site keeps the licensed run above available when a new automated check finishes. [View the history of automated import checks](https://github.com/mklarmann/sentier-agribalyse/actions/workflows/import-run.yml).
