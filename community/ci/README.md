# Optional GitHub Actions checks

The executable checks run locally with `python3 scripts/community.py check` and `python3 -m unittest discover -s community/tests`.

The supplied github-actions.yml is a template, not an enabled workflow. A maintainer with workflow write permissions can copy it to .github/workflows/community.yml to run the same checks on pushes and pull requests. The setup token lacks that GitHub scope; existing workflows remain unchanged.
