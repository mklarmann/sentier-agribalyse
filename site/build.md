# Import and build

This workspace serves no built database. AGRIBALYSE 3.2 is built on ecoinvent 3.9.1, which is licensed data, so nothing built from it can be published here. What the repository gives you is the import: you run it on your own machine, with ADEME's export and your own ecoinvent licence.

The findings and the feedback to ADEME do not depend on a build. A finding is measured on the files that ADEME published.

## What you need

| What | Where it comes from |
|---|---|
| ADEME's export of AGRIBALYSE 3.2 | ADEME, under its own terms. It is not in the repository. |
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
| 1. Your licensed files | Once: the files of the ecoinvent background are made on your machine from your own licence, as [BOOTSTRAP.md](../BOOTSTRAP.md) describes. | An ecoinvent 3.9.1 licence |
| 2. Registry | `dds-build-registry` and the four builders after it put every mapping, flow list and factor table under `source/` into one registry. Every later step reads the registry. | ADEME's export and the files of stage 1 |
| 3. Link | `dds-link-all` reads ADEME's export, applies the curated changes listed below and links every input to its supplier and every elementary flow to its flow in the method. It writes the linked system and a report of the run. | The registry |
| 4. Score | `dds-backtest` scores every mapped product with the 19 headline EF 3.1 methods and compares each score with ADEME's reference value. | The linked system |
| 5. Look | `dds-compare-cfs` and `dds-build-flow-decomp` write the data of the dashboard, which shows each score beside ADEME's and what a difference comes from. | The scores |
| 6. Export | Optional: `dds-build-bw-package` writes the linked system as a Brightway package with its own importer. The package holds ecoinvent data and stays on your machine. | The linked system |

Keep what the build was made from beside it: the release, the hashes of the source files, the background version, the method source, the mappings and any parameter overrides. [How builds are checked](../community/build-validation.md) says what the checks on a build cover and what they do not.

**No run is shown on this page.** GitHub has neither ADEME's export nor an ecoinvent licence, so it can run no stage on the real data. What it runs on every change is the import's own tests, on made-up data, and the checks of this workspace.

## What the import changes in ADEME's export

The import does not use the export as it is. Its curated changes are files in the repository, each with a description of its own, and each open to review:

- [`agribalyse-3.2-delete-aggregated-ecoinvent-processes.json`](../source/agribalyse-3.2-delete-aggregated-ecoinvent-processes.json) and [`agribalyse-3.2-delete-aggregated-ecoinvent-products.json`](../source/agribalyse-3.2-delete-aggregated-ecoinvent-products.json) take out the aggregated ecoinvent processes that the export carries, and their products. Your own ecoinvent takes their place.
- [`agribalyse-3.2-correct-ecoinvent-edge-labels.json`](../source/agribalyse-3.2-correct-ecoinvent-edge-labels.json) corrects the labels of inputs that name such a process, so that they link to ecoinvent.
- [`agribalyse-3.2-extra-unit-conversions.json`](../source/agribalyse-3.2-extra-unit-conversions.json) holds unit conversions that inputs of AGRIBALYSE need and the general list does not have.
- [`curated_overrides.json`](../source/curated_overrides.json) holds hand-curated synonyms for elementary flows that link by no other rule.
- [`agribalyse-3.2-activity-location-overrides.json`](../source/agribalyse-3.2-activity-location-overrides.json) names the location of a few activities whose name in the export gives another one than ADEME's reference results use. Each entry says why.

None of these is ADEME's correction. A change of this sort is proposed as a pull request to the import; an observation about ADEME's data is a [finding](findings.md).

## What stays on your machine

- ADEME's export and everything derived from the ecoinvent background: the snapshots, the factor tables keyed by ecoinvent flows, the scoring caches and the Brightway package.
- Anything from a release that ADEME has not published.

The repository's `.gitignore` and its pre-commit guard keep these files out of a commit. [Data and terms](../community/data-and-attribution.md) says which terms apply to what.

## Apply a contribution

A [contribution](contributions.md) is applied in your own build, beside the unchanged one. Work in a separate checkout with its own source, cache, registry and output folders. Keep the background, the units, the allocation, the boundary, the geography and the method the same in both builds, unless the contribution is about one of them. [Application and testing](../community/application-and-testing.md) describes the comparison.
