# Import and build

Follow AGRIBALYSE 3.2 from ADEME’s export to a scored inventory on ecoinvent 3.9.1. Select a stage to read the terminal output recorded on the licensed machine. The Score stage shows how closely the results reproduce ADEME’s reference values. Export shows what happens when the licensed background is stripped and restored.

<!-- generated: last-run -->

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
