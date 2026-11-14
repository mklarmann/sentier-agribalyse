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

Then follow [BOOTSTRAP.md](../BOOTSTRAP.md) for the files that come from your ecoinvent licence, and [the import reference](../IMPORT.md) for the commands. The import builds the mapping registry, links the flows, registers the 19 headline EF 3.1 methods, compares its scores with ADEME's reference results and writes a Brightway package.

Keep what the build was made from beside it: the release, the hashes of the source files, the background version, the method source, the mappings and any parameter overrides. [How builds are checked](../community/build-validation.md) says what the checks on a build cover and what they do not.

## What stays on your machine

- ADEME's export and everything derived from the ecoinvent background: the snapshots, the factor tables keyed by ecoinvent flows, the scoring caches and the Brightway package.
- Anything from a release that ADEME has not published.

The repository's `.gitignore` and its pre-commit guard keep these files out of a commit. [Data and terms](../community/data-and-attribution.md) says which terms apply to what.

## Apply a contribution

A [contribution](contributions.md) is applied in your own build, beside the unchanged one. Work in a separate checkout with its own source, cache, registry and output folders. Keep the background, the units, the allocation, the boundary, the geography and the method the same in both builds, unless the contribution is about one of them. [Application and testing](../community/application-and-testing.md) describes the comparison.
