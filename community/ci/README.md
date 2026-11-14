# Checks and automation

[The Checks workflow](../../.github/workflows/checks.yml) runs on every pull request and on every push to `main`: the records, the shared files, the unit tests of the workspace, and a build of the site from the records alone with its link check. It needs none of ADEME's data and no ecoinvent licence, and it deploys nothing. The import's own lint and tests stay in [ci.yml](../../.github/workflows/ci.yml).

Run the same checks on your own machine:

```sh
python3 scripts/community.py check
python3 scripts/shared_files.py check
uv run --no-project --python 3.12 --with markdown==3.7 python -m unittest discover -s community/tests
python3 scripts/build_checks.py community/templates/build-audit.json
uv run --no-project --python 3.12 --with markdown==3.7 python scripts/build_site.py --offline --out _site
uv run --no-project --python 3.12 python scripts/check_site.py _site
```

[The Site workflow](../../.github/workflows/pages.yml) deploys the site; [site/README.md](../../site/README.md) describes it, and says which automations of sentier-bafu are not switched on here yet.

`github-actions.yml` here is a standalone copy of the checks for a repository that wants only them. The portable `.gitlab-ci.yml` runs the same checks and publishes the site for a GitLab mirror.
