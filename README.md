<p><img src="site/assets/sentier.svg" alt="sentier.dev" width="160"></p>

# AGRIBALYSE · a shared dataset workspace

**Reproduce the import. Bring contributions into application and testing. Build reviewed consensus and return actionable recommendations to ADEME.**

This public Sentier project combines the existing AGRIBALYSE adapter with a central space for partner evidence, hackathon contributions, candidate improvements and source-dataset discussions. The project spans releases; its current documented adapter imports **AGRIBALYSE 3.2** with **ecoinvent 3.9.1** and **EF 3.1**. Public participation requires no private or unreleased adapter.

[Import and build](IMPORT.md) · [Findings](site/findings.md) · [Take part](site/take-part.md) · [Contributions](community/workflow.md) · [How builds are checked](community/build-validation.md)

## Start with the existing adapter

The adapter imports ADEME's SimaPro CSV, links through a tiered MappingRegistry, registers the 19 headline EF 3.1 methods, backtests against ADEME reference results and exports a parity-checked Brightway package. The detailed commands, prerequisites, solver setup, parameter tools and architecture remain in [the import and application reference](IMPORT.md).

```sh
git clone https://github.com/sentier-dev/sentier-agribalyse.git
cd sentier-agribalyse
uv sync --extra test
```

ADEME's export ships in the repository without its embedded ecoinvent datasets. Obtain the licensed background inputs locally; follow [BOOTSTRAP.md](BOOTSTRAP.md) and [IMPORT.md](IMPORT.md). Source snapshots, background-derived CF tables, scoring caches and Brightway exports remain gitignored; the pre-commit guard also refuses the ones holding ecoinvent amounts, CFs or the dataset list. The code licence does not relicense those artifacts.

## Bring evidence, then test the claim

| Step | What belongs here |
|---|---|
| Canonical import | Source release, hashes, background version and reproducible adapter path |
| Partner contributions | Findings, curated mappings, parameter scenarios and process models |
| Application & testing | Isolated candidates, named exchange changes, coverage and equivalent-scope comparisons |
| Reviewed consensus | Actual reviewer decisions, objections and their disposition |
| Recommendations to ADEME | Agreed findings, delivery evidence and provider responses |

A **source finding** needs reproduction against the named AGRIBALYSE release. An **adapter defect** needs evidence of the transformation that introduced it. A **scenario** needs assumptions and application tests; it is not automatically a correction of ADEME's data. [Open a finding](site/take-part.md#identify-a-finding), [start a discussion](https://github.com/sentier-dev/sentier-agribalyse/issues/new?title=%5BDiscussion%5D%20), or start with [a contribution record](community/templates/contribution.json). A finding gets a record of its own under `community/findings/`; its status is computed from the dated evidence in that record.

Reuse the existing MappingRegistry, parameter overrides, dangling-edge auditor, backtests and export parity verifier. The [application guide](community/application-and-testing.md) explains how to retain separate baseline and candidate builds.

## Shared lessons from the BAFU workspace

[Lessons from the BAFU/UVEK workspace](community/lessons-from-bafu.md) brings relevant lci-bafu-catalog lessons into AGRIBALYSE:

- Account for source, imported and served exchange counts through named changes.
- Audit final biosphere characterization separately from successful linking: a flow that links but has no factor scores zero without an error. `scripts/build_checks.py` checks this on a submitted build audit; a check inside the adapter's emit stage continues on a branch of its own, and a pull request for it follows this one.
- Keep exact input/output hashes alongside a portable aggregate-summary identity. The summary is not a complete inventory fingerprint.
- Give reconstructed inventories separate identities and evidence. BAFU-specific values, prefixes and factor choices are not copied into AGRIBALYSE.

```sh
python3 scripts/community.py check
python3 scripts/shared_files.py check
uv run --no-project --python 3.12 --with markdown==3.7 python -m unittest discover -s community/tests
python3 scripts/build_checks.py path/to/build-audit.json
uv run pytest -q
```

Read [build validation](community/build-validation.md) for the checks' precise scope and limitations. These additions are reviewed through [PR #6](https://github.com/sentier-dev/sentier-agribalyse/pull/6); synthetic tests do not establish a newly reproduced licensed baseline or new partner consensus.

## The site

The site is built from the records: a page per finding and per contribution, the feedback to ADEME, and how to import and build AGRIBALYSE yourself. It serves no built database. It has the same frame as [the BAFU/UVEK site](https://sentier-dev.github.io/sentier-bafu/) and its own index colour, so that a reader sees which dataset they are on.

The scripts that check the records and build the site are shared with sentier-bafu, and `python3 scripts/shared_files.py check` holds them to the same files. [The Checks workflow](.github/workflows/checks.yml) runs on pull requests, and [the Site workflow](.github/workflows/pages.yml) publishes from `main` at `https://sentier-dev.github.io/sentier-agribalyse/` once a maintainer has enabled **Settings → Pages → Source: GitHub Actions**. Build it on your own machine with the commands in [site maintenance](site/README.md).

## Data, credit and participation

Code: MIT. ADEME source material and ecoinvent backgrounds retain their applicable terms; [data and attribution](community/data-and-attribution.md) explains the artifact distinctions. Licensed inputs and confidential evidence stay local. Reviewer agreement and provider responses require evidence in [the workflow](community/workflow.md) and [recommendation tracker](community/recommendations/tracker.json).
