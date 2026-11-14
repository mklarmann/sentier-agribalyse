# Import and build

The import takes ADEME's export to a scored and linked system in six stages. One of them runs here, in public, on every change. The other five need an ecoinvent 3.9.1 licence: they run on your own machine, with the import this repository gives you. This is the last run, as it happened.

<!-- generated: last-run -->

This workspace serves no built database. AGRIBALYSE 3.2 is built on ecoinvent 3.9.1, which is licensed data, so nothing built from it can be published here. The findings and the feedback to ADEME do not depend on a build: a finding is measured on the files that ADEME published.

## What you need

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
| 1. ADEME's export | The shipped export is unpacked, compared with the checksum recorded beside it, and its processes are counted. This is the stage that runs here. | Nothing but the repository |
| 2. Licensed files | Once: the files of the ecoinvent background are made on your machine from your own licence, as [BOOTSTRAP.md](../BOOTSTRAP.md) describes. | An ecoinvent 3.9.1 licence |
| 3. Registry | `dds-build-registry` and the four builders after it put every mapping, flow list and factor table under `source/` into one registry. Every later stage reads the registry. | The files of stage 2 |
| 4. Link | `dds-link-all` reads ADEME's export, applies the curated changes listed below and links every input to its supplier and every elementary flow to its flow in the method. It writes the linked system and a report of the run. | The registry |
| 5. Score | `dds-backtest` scores every mapped product with the 19 headline EF 3.1 methods and compares each score with ADEME's reference value. `dds-compare-cfs` and `dds-build-flow-decomp` write the data of the dashboard, which shows each score beside ADEME's. | The linked system |
| 6. Export | Optional: `dds-build-bw-package` writes the linked system as a Brightway package with its own importer. The package holds ecoinvent data and stays on your machine. | The linked system |

Keep what the build was made from beside it: the release, the hashes of the source files, the background version, the method source, the mappings and any parameter overrides. [How builds are checked](../community/build-validation.md) says what the checks on a build cover and what they do not.

GitHub has no ecoinvent licence, so it runs the first stage and no later one: on every change to the export or to the run, once a month, and when a maintainer asks for it. The run at the top of this page is the last of those, also when it failed. Nothing in it is written by hand: the numbers come from the account the run kept, and the lines are the lines it printed. On every change GitHub also runs the import's own tests, on made-up data, and the checks of this workspace.

## What the import changes in ADEME's export

The import does not use the export as it is. Its curated changes are files in the repository, each with a description of its own, and each open to review:

- [`agribalyse-3.2-delete-aggregated-ecoinvent-processes.json`](../source/agribalyse-3.2-delete-aggregated-ecoinvent-processes.json) and [`agribalyse-3.2-delete-aggregated-ecoinvent-products.json`](../source/agribalyse-3.2-delete-aggregated-ecoinvent-products.json) take out the aggregated ecoinvent processes that the export carries, and their products. Your own ecoinvent takes their place.
- [`agribalyse-3.2-correct-ecoinvent-edge-labels.json`](../source/agribalyse-3.2-correct-ecoinvent-edge-labels.json) corrects the labels of inputs that name such a process, so that they link to ecoinvent.
- [`agribalyse-3.2-extra-unit-conversions.json`](../source/agribalyse-3.2-extra-unit-conversions.json) holds unit conversions that inputs of AGRIBALYSE need and the general list does not have.
- [`curated_overrides.json`](../source/curated_overrides.json) holds hand-curated synonyms for elementary flows that link by no other rule.
- [`agribalyse-3.2-activity-location-overrides.json`](../source/agribalyse-3.2-activity-location-overrides.json) names the location of a few activities whose name in the export gives another one than ADEME's reference results use. Each entry says why.

None of these is ADEME's correction. A change of this sort is proposed as a pull request to the import; an observation about ADEME's data is a [finding](findings.md).

## What stays on your machine

- ADEME's full export, with the ecoinvent datasets it carries, and everything derived from the ecoinvent background: the snapshots, the factor tables keyed by ecoinvent flows, the scoring caches and the Brightway package.
- Anything from a release that ADEME has not published.

The repository's `.gitignore` and its pre-commit guard keep these files out of a commit. [Data and terms](../community/data-and-attribution.md) says which terms apply to what.

## Apply a contribution

A [contribution](contributions.md) is applied in your own build, beside the unchanged one. Work in a separate checkout with its own source, cache, registry and output folders. Keep the background, the units, the allocation, the boundary, the geography and the method the same in both builds, unless the contribution is about one of them. [Application and testing](../community/application-and-testing.md) describes the comparison.
