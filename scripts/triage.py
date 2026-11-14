"""Join the finding records with what only the issue tracker knows.

Where a finding stands is computed from the dated evidence in its record (community.stage);
the tracker never decides it. GitHub adds comment counts, last activity, labels, and issues
filed as findings that have no record yet. Without the tracker everything still builds from
the records.

    load_issues(repository, snapshot, offline, require)   {number: issue}, and where it came from
    assemble(findings, repository, issues, patches)       the joined view the site is built from:
        findings            every record as a dict with these added keys:
                              stage         the stage key (community.stage)
                              path          the record's file in the repository
                              tracker       the issue's data from GitHub, or None
                              steps         the five steps of its path, from its evidence (steps())
                              patches       the community patches that answer it
                              related       related findings, both directions
                              changed       date of its newest evidence
                              waiting_since that date while it is still on the path, else None
        counts              {stage key: number of findings}
        unlisted            open finding issues that have no record yet
        without_issue       ids of records that have no issue in this repository
        label_differences   for maintainers: issues whose labels do not match their record
    steps(record)                                         the five steps of a finding's path, each
                                                          done only when the record holds its evidence
    expected_labels(stage)                                the labels a record's issue should carry
"""

import json
import os
import time
import urllib.request
from pathlib import Path

import community
import sync  # scripts/sync.py writes the labels; here they are only compared

FINDING_LABEL = sync.FINDING_LABEL
HELP_LABEL = sync.HELP_LABEL
# Labels of the earlier model, and the form's `needs-triage`, which now means only
# "an issue without a record": none of them belongs on an issue that has a record.
RETIRED_LABELS = sync.RETIRED_LABELS | {sync.TRIAGE_LABEL}


def slug(repository):
    return repository.rstrip("/").split("github.com/")[-1]


def read_json(request, tries=3):
    """One request, tried again twice: a deploy must not fail on a single dropped connection."""
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.load(response)
        except OSError:
            if attempt == tries - 1:
                raise
            time.sleep(1 + attempt)


def fetch_issues(repository, token=None):
    """The repository's finding issues as {number: issue}: one request per hundred."""
    issues, page = {}, 1
    while True:
        request = urllib.request.Request(
            f"https://api.github.com/repos/{slug(repository)}/issues"
            f"?state=all&labels={FINDING_LABEL}&per_page=100&page={page}",
            headers={"Accept": "application/vnd.github+json", "User-Agent": "sentier-site-build"},
        )
        if token:
            request.add_header("Authorization", f"Bearer {token}")
        batch = read_json(request)
        for item in batch:
            if "pull_request" in item:
                continue
            issues[item["number"]] = {
                "number": item["number"],
                "title": item["title"],
                "state": item["state"],
                "labels": sorted(label["name"] for label in item["labels"]),
                "comments": item["comments"],
                "updated": item["updated_at"][:10],
                "url": item["html_url"],
            }
        if len(batch) < 100:
            return issues
        page += 1


def load_issues(repository, snapshot=None, offline=False, require=False):
    """Issues from a snapshot file, else the API. ({}, None) when neither is available,
    unless `require` is set: a published site must not lose its discussion data silently."""
    if snapshot and Path(snapshot).exists():
        data = json.loads(Path(snapshot).read_text())
        return {int(k): v for k, v in data["issues"].items()}, data.get("fetched", "snapshot")
    if offline:
        return {}, None
    try:
        return fetch_issues(repository, os.environ.get("GITHUB_TOKEN")), "live"
    except Exception as error:
        if require:
            raise SystemExit(f"Could not read the issues of {repository}: {error}") from error
        print(f"Issues not read ({type(error).__name__}); building from the records alone.")
        return {}, None


def expected_labels(stage, provider=None):
    """The labels an issue should carry for a record at this stage. Labels follow records."""
    return sync.expected_labels(stage, provider or community.load_config()["provider"])


def label_differences(placed, issues):
    """For maintainers and the label sync, never for a public page: issues whose labels do
    not match their record. An issue shared by several findings shows the earliest stage."""
    by_issue = {}
    for finding in placed:
        if finding["issue"] in issues:
            by_issue.setdefault(finding["issue"], []).append(finding)
    differences = []
    for number, findings in sorted(by_issue.items()):
        earliest = min((f["stage"] for f in findings), key=community.STAGE_ORDER.get)
        expected = expected_labels(earliest)
        present = set(issues[number]["labels"])
        add = sorted(expected - present)
        remove = sorted(label for label in present if sync.owned(label) and label not in expected)
        if add or remove:
            ids = sorted((f["id"] for f in findings), key=lambda rid: int(rid[1:]))
            differences.append(dict(issue=number, findings=ids, stage=earliest, add=add, remove=remove))
    return differences


# The path of a finding: one step per piece of dated evidence, in order.
PATH = ("reported", "repeated", "sent", "answer", "fixed_in")


def steps(record):
    """The five steps of a finding's path: [{key, state, block}], decided by the record's evidence alone.

    state is one of
        done        the record holds the evidence of this step
        now         the step the finding waits at
        help        it waits for a second measurement, which anyone can supply
        unrecorded  a later step is recorded and this one is not: never shown as done
        todo        not reached
    A closed finding, and one the provider declined to change, waits at nothing.
    """
    def held(key):
        block = record.get(key)
        if key == "repeated":
            return bool(block) and block.get("result") == "reproduced"
        return bool(block)

    has = [held(key) for key in PATH]
    last = max(n for n, yes in enumerate(has) if yes) if any(has) else -1
    waits = not record.get("closed") and (record.get("answer") or {}).get("outcome") != "declined"
    placed = []
    for n, key in enumerate(PATH):
        if has[n]:
            state = "done"
        elif n < last:
            state = "unrecorded"
        elif n == last + 1 and waits:
            state = "help" if key == "repeated" else "now"
        else:
            state = "todo"
        placed.append({"key": key, "state": state, "block": record.get(key)})
    return placed


def assemble(findings, repository, issues, patches=None):
    """Findings with their stage and discussion, plus finding issues that have no record yet."""
    by_finding = community.patches_by_finding(patches)
    relations = community.related(findings)
    placed, counts = [], {}
    for record in findings:
        stage = community.stage(record)
        counts[stage] = counts.get(stage, 0) + 1
        placed.append(
            dict(
                record,
                stage=stage,
                path=getattr(record, "path", None) or community.record_path(record),
                tracker=issues.get(record["issue"]) if record["issue"] else None,
                steps=steps(record),
                patches=by_finding.get(record["id"], []),
                related=relations[record["id"]],
                changed=community.last_change(record),
                waiting_since=community.waiting_since(record),
            )
        )
    placed.sort(key=lambda f: (community.STAGE_ORDER[f["stage"]], -community.finding_number(f)))
    cited = {f["issue"] for f in placed if f["issue"]}
    unlisted = [i for n, i in sorted(issues.items()) if n not in cited and i["state"] == "open"]
    return dict(
        findings=placed,
        unlisted=unlisted,
        counts=counts,
        without_issue=sorted((f["id"] for f in placed if not f["issue"]), key=lambda rid: int(rid[1:])),
        label_differences=label_differences(placed, issues),
    )
