# Public documentation site

The site uses Sentier's existing green wordmark and a shared, responsive layout with the AGRIBALYSE workspace. Logo source: [sentier-dev/Branding](https://github.com/sentier-dev/Branding). Content comes only from the explicit Markdown file list in `site/config.json` and contribution metadata. Inventory directories, licensed backgrounds, private evidence, scoring caches and binary exports are never build inputs.

```sh
uv run --no-project --with markdown==3.7 scripts/build_site.py
python3 scripts/check_site.py _site
python3 -m http.server 8765 --bind 127.0.0.1 --directory _site
```

The generated `_site/` directory is ignored. Links, counts and contribution status are generated from repository records. The site claims no newly accepted consensus or delivered recommendations. The portable GitLab pipeline runs coordination tests and publishes only the site from the default branch. It does not build or upload inventories.

GitHub Pages is deployed by [the Documentation workflow](../.github/workflows/pages.yml) after a push to `main`. Pull requests build and check the site without deploying it. A repository administrator enables Pages once with **Settings → Pages → Source: GitHub Actions**. The workflow uploads only `_site/`, and installs the Markdown builder independently of the inventory adapter. The same generated site also works on GitLab Pages through `.gitlab-ci.yml`. Hosting links and any outstanding maintainer step are recorded in the main README.

Update both projects' shared renderer, stylesheet and validation tooling together. Update dataset-specific content in `site/config.json` and the listed Markdown sources. The summary identity is not an inventory hash, and technical validation is not a reviewer approval.
