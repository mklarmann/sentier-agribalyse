# Import and build

We ran the same AGRIBALYSE 3.2 import on ecoinvent 3.9.1 using two source files. The climate check asks whether at least 99% of comparable foods fall within 5% of ADEME’s published result.

<!-- source comparison -->

| AGRIBALYSE 3.2 input | Foods within 5% of ADEME | Outside tolerance | 99% target |
|---|---|---:|---|
| Distributable source | 2,163 of 2,450 (88.3%) | 287 | Missed |
| Full licensed source | 2,446 of 2,450 (99.8%) | 4 | Passed |

<!-- end source comparison -->

The distributable file omits 210 processes that ADEME adapted from ecoinvent. Where reconstruction is incomplete, the import can link to an unmodified supplier or leave an input unlinked. The full licensed file retains those adaptations. [Why the source changed](https://github.com/sentier-dev/sentier-agribalyse/pull/15) · [See the verification run](runs.md#full-source-verification).

Both inputs produced a local Brightway export. The distributable input also passed the strip-and-refill check. The exporter stopped the full-source inventory from being packaged for sharing because it still contains licensed ecoinvent blocks.

The replay below follows the **distributable source** through all six stages. Select **Score** for its climate check or **Export** for the strip-and-refill test.

<!-- generated: last-run -->

## Download and reproduce the inventories

[Download the foreground inventory and rebuild kit (ZIP)](https://github.com/mklarmann/sentier-agribalyse/releases/download/agribalyse-3.2-review-2026-11-19/agribalyse-3.2-foreground.zip) · [Download the patched foreground exchanges (compressed CSV)](https://github.com/mklarmann/sentier-agribalyse/releases/download/agribalyse-3.2-review-2026-11-19/patched-foreground-exchanges.csv.gz)

The kit contains the 17,966-process source export, the patched foreground and the expected food scores. Extract it and follow `README.txt` to reconnect your own ecoinvent 3.9.1 cut-off background. The second download contains the linked foreground exchanges after patching. Its rows identify the AGRIBALYSE process, the product or elementary-flow row and the signed matrix coefficient. The row identifiers match the locally rebuilt scoring package.

[Download ADEME and patched results side by side (CSV)](https://github.com/mklarmann/sentier-agribalyse/releases/download/agribalyse-3.2-review-2026-11-19/food-comparison.csv)

## What you need

The [source register](sources.md) identifies the public inputs. [Case F7](cases/F7.html) traces the elementary flow list from a user’s question to the download command used to prepare the import.

| What | Where it comes from |
|---|---|
| ADEME's export of AGRIBALYSE 3.2 | In the repository, without the ecoinvent datasets it carried: `source/AGB32_ecoinvent_free.CSV.xz`. ADEME publishes AGRIBALYSE under the Etalab Open Licence 2.0. |
| The list of elementary flows | `dds-fetch-harmonised-flows` downloads it once (Brightway Flows, under the ODbL). |
| ecoinvent 3.9.1 | Your own licence. The repository holds no ecoinvent data, and a guard refuses to commit any. |
| The EF 3.1 methods | Read by the import from their published sources. |
| The import | This repository: the code, the curated mappings and the tests. |

## Import and build it yourself

```sh
git clone https://github.com/sentier-dev/sentier-agribalyse.git
cd sentier-agribalyse
uv sync --extra test
```

Then follow the steps below. [BOOTSTRAP.md](../BOOTSTRAP.md) covers the files that come from your ecoinvent licence, and [the import reference](../IMPORT.md) has every command with its options.

## The steps, from ADEME's export to a build

| Stage | What happens | What it needs |
|---|---|---|
| 1. ADEME's export | The shipped export is unpacked, compared with the checksum recorded beside it, and its processes are counted. The checksum and process count are checked against the manifest. | Nothing but the repository |
| 2. Licensed files | The run reads the background and method snapshots prepared under the local licence, as [BOOTSTRAP.md](../BOOTSTRAP.md) describes. | An ecoinvent 3.9.1 licence |
| 3. Registry | `dds-build-registry` and the four builders after it put every mapping, flow list and factor table under `source/` into one registry. Every later stage reads the registry. | The files of stage 2 |
| 4. Link | `dds-link-all` reads ADEME's export, applies the curated mappings and resolves supplier and elementary-flow links. It writes the linked system and a report of the run. | The registry |
| 5. Score | `dds-backtest` scores every mapped product with the 19 headline EF 3.1 methods and compares each score with ADEME's reference value. `dds-compare-cfs` and `dds-build-flow-decomp` write the data of the dashboard, which shows each score beside ADEME's. | The linked system |
| 6. Export | `dds-build-bw-package` writes a local Brightway package. `dds-build-skeleton` strips the licensed columns from a separate scoring package. The run refills it and compares its matrices and scores with the original. | The linked system |

Keep what the build was made from beside it: the release, the hashes of the source files, the background version, the method source, the mappings and any parameter overrides. [How builds are checked](../community/build-validation.md) says what the checks on a build cover and what they do not.

See [Mapping](mapping.md) for the rules the import applies and [Inventory quality](../community/build-validation.md) for the evidence about the resulting inventory.

## What stays on your machine

- ADEME's full export, with the ecoinvent datasets it carries, and everything derived from the ecoinvent background: the snapshots, the factor tables keyed by ecoinvent flows, the scoring caches and the Brightway package.
- Anything from a release that ADEME has not published.

The repository's `.gitignore` and its pre-commit guard keep these files out of a commit. [Data and terms](../community/data-and-attribution.md) says which terms apply to what.

## Apply a contribution

A [contribution](contributions.md) is applied in your own build, beside the unchanged one. Work in a separate checkout with its own source, cache, registry and output folders. Keep the background, the units, the allocation, the boundary, the geography and the method the same in both builds, unless the contribution is about one of them. [Application and testing](../community/application-and-testing.md) describes the comparison.
