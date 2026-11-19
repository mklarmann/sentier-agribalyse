# Public site

The site is built from the records, not written by hand: one page per finding and per contribution, a page per AGRIBALYSE release, the overview, what changed, and the pages of prose named in `site/config.json`.

```sh
uv run --frozen scripts/inventory_quality.py --check
uv run --no-project --python 3.12 --with markdown==3.7 --with 'sentier-diagnostics @ git+https://github.com/sentier-dev/sentier-diagnostics@4740326dd6d1b662f01d29d8ac98419979487fbb' python scripts/build_site.py --last-run site/licensed-run.json --offline --out _site
uv run --no-project --python 3.12 python scripts/check_site.py _site
python3 -m http.server 8765 --bind 127.0.0.1 --directory _site
```

`_site/` is ignored. ADEME's export, the ecoinvent background, scoring caches and Brightway packages are never build inputs, and `check_site.py` refuses data file types. The site links to the local rebuild instructions. AGRIBALYSE 3.2 is built on a licensed background.

## Compare locally scored products

The public Comparison page shows counts by build step. In the catalogue, **ADEME impact results** shows the reference values from ADEME’s open food table, including its published treatment of packaging corrections. Run `python3 scripts/build_catalogue.py` to refresh the catalogue and these values.

For individual before/after rebuild scores, point the following command at the five licensed local build checkouts and the two repeat runs. Each checkout must retain its run report, source export and scored Parquet. The generator checks the export fingerprints and product identifiers. The optional explorer opens directly from disk with the complete local matrix. The counts file is suitable for review independently.

```sh
mkdir -p .local
uv run --frozen --with 'sentier-diagnostics @ git+https://github.com/sentier-dev/sentier-diagnostics@4740326dd6d1b662f01d29d8ac98419979487fbb' python scripts/compare_review_builds.py \
  --baseline "$BUILDS/fb-nb-main-a-adapter" --repeat-baseline "$BUILDS/fb-nb-main-b2-adapter" \
  --codes "$BUILDS/fb-nb-a-adapter" --repeat-codes "$BUILDS/fb-nb-a2-adapter" \
  --flows "$BUILDS/fb-nb-ac-adapter" --water "$BUILDS/fb-nb-acw-adapter" \
  --integrated "$BUILDS/fb-review-nov18-adapter" --out .local/counts.json --local-explorer
open .local/review-explorer/index.html
```

Set `BUILDS` to the folder containing the build checkouts. Without `--local-explorer`, the same command writes only aggregate counts. The page published by Pages does not read the ignored `.local/` directory.

## Shared with sentier-bafu

The scripts that check the records and build the site (`scripts/build_site.py`, `check_site.py`, `community.py`, `triage.py`, `intake.py`, `sync.py`, `github_api.py`, `last_run.py` and the folders `scripts/sitebuild` and `scripts/runrecord`), the stylesheet, the two scripts of the pages, the font, the logo and the schemas of the records are the same files as in [sentier-bafu](https://github.com/sentier-dev/sentier-bafu). They are written and tested there. Its site guide, `site/README.md` at the commit that `site/shared.json` names, is the reference for them: the generated blocks a page of prose can ask for, the words for a status, the keys of `site/config.json`, and the data files of the site.

`site/shared.json` names every shared file with its checksum, and the commit of sentier-bafu it was taken from.

```sh
python3 scripts/shared_files.py check
python3 scripts/shared_files.py take ../sentier-bafu --commit <commit>
```

`check` fails when a shared file differs from the one named, or when a shared folder holds a file that is not named. Do not edit a shared file here: change it in sentier-bafu, then `take` it again. The Checks workflow runs `check` on every pull request.

Until the work lands in `sentier-dev/sentier-bafu`, `site/shared.json` names the repository and the branch the commit is in.

## This repository's own

| File | What it is |
|---|---|
| `site/config.json` | the dataset and the provider, the releases, the index colour, the navigation, the pages, the old addresses that lead on |
| `site/findings.md`, `feedback.md`, `contributions.md`, `build.md`, `take-part.md`, `data.md` | the pages of prose |
| `.github/ISSUE_TEMPLATE/agribalyse-data-finding.yml` | the form for a finding; its headings are read by `scripts/intake.py` |
| `scripts/shared_files.py`, `scripts/build_checks.py` | the check of the shared files; the checks on a build audit |
| `community/tests/test_workspace.py` | the tests of this repository's records, forms and site |

What differs from sentier-bafu, and why:

- **No patched release and no release build.** `site/config.json` lists no page for one, so the build reads no release build and no page links to one. The Build page replays the reviewed local import from `site/licensed-run.json`. That public record contains stage timings, terminal output and aggregate diagnostics.
- **Releases.** A release is one entry under `releases`, with the background it is built on. Register a release only after ADEME has published it; a test holds the list to the published releases.
- **Processes have a name and a process identifier of letters and digits, and no number.** The shared record format lists datasets by number, so `dataset_code_pattern` is left out. A finding lists no datasets and says in `scope` what it is about, for a single process with its process identifier.
- **Numbers.** `older_numbering_until` is 0: the number of a finding is the number of its issue.
- **The index colour.** `index` is aubergine, `#5d4a66`, with its dark, soft and tint shades. Every Sentier dataset site has the same frame (the logo, the paper, the type) and its own index colour; BAFU/UVEK has slate blue, `#3e5c76`. The build refuses a colour that cannot be read.

The design follows [Départ de Sentier's website](https://www.d-d-s.ch/): the green logo from [Depart-de-Sentier/dds-logo](https://github.com/Depart-de-Sentier/dds-logo) by Sylvain Prevost (CC BY 4.0), and Nunito from [Google Fonts](https://github.com/google/fonts/tree/main/ofl/nunito) under `site/assets/OFL.txt`.

## Deployment

[The Site workflow](../.github/workflows/pages.yml) deploys to GitHub Pages after a push to `main`, once a day, and when an issue is opened, closed or reopened. It needs **Settings → Pages → Source: GitHub Actions**. Pull requests are built and checked by [the Checks workflow](../.github/workflows/checks.yml), without the network and without deploying. A copy that another repository builds, such as a fork, says on every page that it is not the published site.

Not here yet: the two workflows of sentier-bafu that write to issues. Intake proposes a record as a pull request when an issue is filed with the finding form, and Sync keeps the labels of finding issues in line with the records. Their scripts, `scripts/intake.py` and `scripts/sync.py`, are among the shared files and are tested here on the finding form; the workflows that run them are added when the first findings arrive and a maintainer has agreed to the permissions they need. Until then a maintainer writes a finding's record by hand, from the [template](../community/templates/finding.json).

Pages reads the reviewed aggregate run record in `site/licensed-run.json`. Product-level rebuild scores stay in the local explorer.
