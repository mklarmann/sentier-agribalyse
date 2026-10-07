# Optional GitHub Actions checks

The executable checks run locally with `python3 scripts/community.py check` and `python3 -m unittest discover -s community/tests`.

The supplied github-actions.yml is a template, not an enabled workflow. A maintainer with workflow write permissions can copy it to .github/workflows/community.yml to run the same checks on pushes and pull requests. The setup token lacks that GitHub scope; existing workflows remain unchanged.

The repository also contains a portable `.gitlab-ci.yml`: it validates coordination records, runs the synthetic build-audit regressions, builds the site from the explicit public file list and checks generated links before Pages publication. It becomes active only in a GitLab mirror; it is not an enabled GitHub workflow.

The existing pytest CI now also collects the community record and build-audit regressions through `tests/unit/test_community_records.py`. This connects the contracts to the already enabled CI without requiring a new workflow.
