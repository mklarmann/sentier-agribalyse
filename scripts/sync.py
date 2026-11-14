"""Bring the finding issues into agreement with the records: labels, one comment, the state.

    python3 scripts/sync.py            print the differences; write nothing
    python3 scripts/sync.py --apply    write them

The record decides. A finding's status is computed from the dated evidence in its record, and
this job projects it onto the finding's issue:

- labels: the finding label (`finding_label` in site/config.json), exactly one `status: …` label in the words the site shows, and
  `help wanted` while the finding needs a second measurement. An issue filed as a finding
  that has no merged record carries `needs-triage` instead. A label set by hand is put right
  at the next run;
- one comment when the status changes, never two: the comment carries a hidden marker;
- the issue is closed when the status is final (corrected, withdrawn, for information).

Nothing here is a second copy to keep in step: delete every label and run this again, and the
issues say what the records say. Standard library only; `.github/workflows/sync.yml` runs it.

    label_for(key, provider)                 the label of a status
    expected_labels(key, provider)           the labels the issue of a finding carries
    plan(findings, issues, config)           the differences, as plain data; no network
    apply(differences, api, ...)             writes them, an issue at a time, and can be resumed
    report(differences, ...)                 the differences in words
"""

import argparse
import datetime
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import community  # noqa: E402
from github_api import ApiError, GitHub, NotFound, RateLimited, plain, quoted, repository_slug  # noqa: E402

ROOT = community.ROOT
FINDING_LABEL = community.load_config()["finding_label"]  # this repository's label for a finding
HELP_LABEL = "help wanted"
TRIAGE_LABEL = "needs-triage"
CONTRIBUTION_LABEL = "contribution"
STATUS_PREFIX = "status: "
# Labels of the earlier model. None of them is written any more; each is taken off.
RETIRED_LABELS = {"upstream-reported", "upstream-fixed", "informational", "handled-in-layer", "withdrawn"}
FINAL = {"fixed": "completed", "withdrawn": "not_planned", "not-a-defect": "not_planned"}
# Requests kept for the other workflows of the repository when the limit runs low.
RESERVE = 25
STATUS_COLOURS = {
    "filed": "b8860b",
    "confirmed": "84ae99",
    "sent": "84ae99",
    "answered": "3c5343",
    "fixed": "3c5343",
    "not-a-defect": "d8d5c4",
    "withdrawn": "d8d5c4",
}
WRITTEN = "Written by the sync workflow from the finding's record. Do not set it by hand."


def label_for(key, provider):
    """The label of a status: the words the site shows, so a label never says more than they do."""
    words = community.status_label(key, provider).replace(",", "")
    return STATUS_PREFIX + words[:1].lower() + words[1:]


def status_labels(provider):
    return {label_for(status["key"], provider): status["key"] for status in community.STATUSES}


def expected_labels(key, provider):
    """The labels the issue of a finding carries. `key` is None for an issue without a record."""
    if key is None:
        return {FINDING_LABEL, TRIAGE_LABEL}
    labels = {FINDING_LABEL, label_for(key, provider)}
    if key == "filed":
        labels.add(HELP_LABEL)
    return labels


def owned(label):
    """Labels only this job writes on a finding issue. Whatever else an issue carries is left alone.
    GitHub tells labels apart without regard to case, and so does this job."""
    label = label.casefold()
    return label.startswith(STATUS_PREFIX) or label in RETIRED_LABELS or label in (HELP_LABEL, TRIAGE_LABEL)


def missing(expected, present):
    """The expected labels an issue does not carry, whatever the case of those it carries."""
    carried = {label.casefold() for label in present}
    return sorted(label for label in expected if label.casefold() not in carried)


def surplus(expected, present):
    """The labels of this job an issue carries and should not."""
    wanted = {label.casefold() for label in expected}
    return sorted(label for label in present if owned(label) and label.casefold() not in wanted)


def definitions(provider):
    """The labels this job creates when they are missing: {name: (colour, description)}.

    The status labels, and the two the issue forms set that a new repository does not have:
    a form applies a label only if the label exists.
    """
    wanted = {
        name: (STATUS_COLOURS[key], WRITTEN) for name, key in status_labels(provider).items()
    }
    wanted[TRIAGE_LABEL] = ("ededed", "Filed as a finding; no record of it has been merged yet.")
    wanted[CONTRIBUTION_LABEL] = ("84ae99", "A proposed correction, mapping, model or variant, with its evidence.")
    return wanted


def long_date(text):
    """12 October 2026."""
    if not text:
        return "a date that is not recorded"
    day = datetime.date.fromisoformat(text)
    return f"{day.day} {day:%B} {day.year}"


def quote(text):
    return "\n".join(f"> {line}" for line in text.strip().splitlines())


def announcement(records, config):
    """The comment that says where the findings of an issue stand: generated from the records."""
    provider, site = config["provider"], config["site_url"]
    releases = {release["id"]: release["name"] for release in config["releases"]}
    parts, closing = [], all(community.stage(record) in FINAL for record in records)
    for record in records:
        key = community.stage(record)
        head = (
            f"**[{record['id']}]({site}findings/{record['id']}.html)**: "
            f"status **{community.status_label(key, provider)}**."
        )
        if key == "filed":
            body = (
                f"This issue is recorded as a finding. To help, repeat the measurement on {provider}'s "
                "release files and comment here, beginning with the line `/repeated reproduced` or "
                "`/repeated not-reproduced`; then say what you measured and got."
            )
        elif key == "confirmed":
            block = record["repeated"]
            body = (
                f"{block['by']} repeated the measurement on {long_date(block['date'])} and reproduced it "
                f"([comment]({block['url']})). It has not been reported to {provider} yet."
            )
        elif key == "sent":
            block = record["sent"]
            body = (
                f"Reported to {provider} on {long_date(block['date'])}, in batch {block['batch']} "
                f"([where this is recorded]({block['url']})). {provider} decides what it changes."
            )
        elif key == "answered":
            block = record["answer"]
            outcome = community.OUTCOMES[block["outcome"]]["label"].lower()
            body = (
                f"{provider} answered on {long_date(block['date'])} ({outcome}; "
                f"[where this is recorded]({block['url']})):\n\n{quote(block['summary'])}\n\n"
                "Whether the data changes will show in a later release."
            )
        elif key == "fixed":
            block = record["fixed_in"]
            body = (
                f"The correction was checked in {releases.get(block['release'], block['release'])} on "
                f"{long_date(block['date'])} ([evidence]({block['url']}))."
            )
        else:
            block = record["closed"]
            body = f"Recorded on {long_date(block['date'])}:\n\n{quote(block['reason'])}"
        parts.append(f"{head} {body}")
    if closing:
        parts.append("This issue is closed. The finding stays listed on the site.")
    parts.append("*This comment and the labels of this issue follow the finding's record; a workflow writes them.*")
    return "\n\n".join(parts)


def plan(findings, issues, config):
    """The differences between the records and their issues: plain data, no network.

    `issues` is {number: {"state", "state_reason", "labels": [names]}}; None stands for a
    number that is not an issue of the repository. One entry per issue that differs:
    {"issue", "findings", "stage", "add", "remove", "announce", "marker", "comment", "close",
    "person"}. `person` holds what only a person can decide; this job does not touch it.
    """
    provider = config["provider"]
    current = {label.casefold() for label in status_labels(provider)}
    by_issue = {}
    for record in findings:
        if record["issue"]:
            by_issue.setdefault(record["issue"], []).append(record)
    differences = []
    for number in sorted(set(by_issue) | set(issues)):
        records = sorted(by_issue.get(number, []), key=community.finding_number)
        ids = [record["id"] for record in records]
        issue = issues.get(number)
        entry = dict(issue=number, findings=ids, stage=None, add=[], remove=[], announce=False,
                     marker=None, comment=None, close=None, person=[])
        if issue is None:
            entry["person"].append(
                f"{', '.join(ids)} names issue #{number}, which is not an issue of this repository."
            )
            differences.append(entry)
            continue
        present = set(issue["labels"])
        if not records:
            # Filed as a finding, no merged record: a maintainer has not accepted it yet.
            expected = expected_labels(None, provider) if issue["state"] == "open" else set()
            entry["add"] = missing(expected, present)
            entry["remove"] = [
                label for label in surplus(expected, present)
                if not (label.casefold() == TRIAGE_LABEL and issue["state"] != "open")
            ]
        else:
            # An issue that holds several findings shows the earliest status among them.
            stage = min((community.stage(record) for record in records), key=community.STAGE_ORDER.get)
            expected = expected_labels(stage, provider)
            entry["stage"] = stage
            entry["add"] = missing(expected, present)
            entry["remove"] = surplus(expected, present)
            want = label_for(stage, provider).casefold()
            carried = [label.casefold() for label in present if label.casefold().startswith(STATUS_PREFIX)]
            if want in carried:
                changed = False
            elif any(label in current for label in carried):
                changed = True  # another status of today's vocabulary: the status changed
            else:
                # Labels in other words: the vocabulary changed, the status did not. No label
                # at all: the record is new to its issue.
                changed = not carried
            if changed:
                entry["announce"] = True
                entry["marker"] = "sync: " + " ".join(f"{r['id']}={community.stage(r)}" for r in records)
                entry["comment"] = announcement(records, config)
            final = all(community.stage(record) in FINAL for record in records)
            if final and issue["state"] == "open":
                entry["close"] = FINAL[stage]
            elif not final and issue["state"] != "open":
                entry["person"].append(
                    f"#{number} is closed, but {', '.join(ids)} is still on its way "
                    f"({community.status_label(stage, provider)}). Reopen the issue, or close the finding "
                    "with `python3 scripts/community.py close`."
                )
        if any(entry[key] for key in ("add", "remove", "announce", "close", "person")):
            differences.append(entry)
    return differences


def shape(item):
    return {
        "state": item["state"],
        "state_reason": item.get("state_reason"),
        "labels": sorted(label["name"] for label in item.get("labels", [])),
    }


def read_issues(api, findings):
    """The finding issues of the repository, and every issue a record names: {number: issue}."""
    issues = {}
    for item in api.pages(f"/issues?state=all&labels={quoted(FINDING_LABEL)}"):
        if "pull_request" not in item:
            issues[item["number"]] = shape(item)
    for number in sorted({record["issue"] for record in findings if record["issue"]} - set(issues)):
        try:
            item = api.get(f"/issues/{number}")
        except NotFound:
            item = None
        issues[number] = shape(item) if item and "pull_request" not in item else None
    return issues


def snapshot_issues(path, findings):
    """The same from a saved list (the items of GET /issues), for a run without the network."""
    issues = {
        item["number"]: shape(item)
        for item in json.loads(Path(path).read_text(encoding="utf-8"))
        if "pull_request" not in item
    }
    for record in findings:
        if record["issue"]:
            issues.setdefault(record["issue"], None)
    return issues


def label_changes(existing, provider):
    """Label definitions to create or to describe again: ([(name, colour, description)], [(name, description)])."""
    wanted = definitions(provider)
    existing = {name.casefold(): label for name, label in existing.items()}
    create = [(name, *wanted[name]) for name in sorted(wanted) if name.casefold() not in existing]
    describe = [
        (existing[name.casefold()]["name"], wanted[name][1])
        for name in sorted(wanted)
        if name.casefold() in existing and (existing[name.casefold()].get("description") or "") != wanted[name][1]
    ]
    return create, describe


def apply(differences, api, provider, comments=True, pause=None, reserve=RESERVE):
    """Write the differences, one issue after another:
    (issues done, issues left, why it stopped, [(issue, what failed)]).

    Each issue is finished before the next begins, comment first, so a run that stops half
    way (the rate limit) is continued by the next run and nothing is announced twice. An
    issue that cannot be written (it was locked, moved, deleted) does not hold up the others.
    """
    done, pause, failed = 0, pause or time.sleep, []
    # What is left for a person is no work for this job.
    differences = [entry for entry in differences if any(entry[key] for key in ("add", "remove", "announce", "close"))]
    try:
        existing = {label["name"]: label for label in api.pages("/labels")}
        create, describe = label_changes(existing, provider)
        for name, colour, description in create:
            api.post("/labels", {"name": name, "color": colour, "description": description})
        for name, description in describe:
            api.patch(f"/labels/{quoted(name)}", {"description": description})
        for entry in differences:
            if api.remaining is not None and api.remaining < reserve:
                return done, len(differences) - done - len(failed), "the rate limit is nearly used up", failed
            number = entry["issue"]
            try:
                if entry["announce"] and comments:
                    if api.comment_once(number, entry["marker"], entry["comment"]):
                        pause(1)  # GitHub asks for a pause between writes that notify people
                if entry["add"]:
                    api.post(f"/issues/{number}/labels", {"labels": entry["add"]})
                for label in entry["remove"]:
                    try:
                        api.delete(f"/issues/{number}/labels/{quoted(label)}")
                    except NotFound:
                        pass
                if entry["close"]:
                    api.patch(f"/issues/{number}", {"state": "closed", "state_reason": entry["close"]})
            except RateLimited:
                raise
            except ApiError as error:
                failed.append((number, str(error)))
                continue
            done += 1
    except RateLimited:
        return done, len(differences) - done - len(failed), "the rate limit is used up", failed
    return done, 0, None, failed


def names(labels):
    return ", ".join(json.dumps(plain(label, 60)) for label in labels)


def report(differences, findings, issues, config, today=None, markdown=False):
    """The differences in words: what `--apply` would write, and what needs a person."""
    provider = config["provider"]
    bullet = "- " if markdown else "  "
    with_issue = [record for record in findings if record["issue"]]
    without = [record["id"] for record in findings if not record["issue"]]
    lines = [
        f"Records: {len(findings)} findings; {len(with_issue)} are discussed in "
        f"{len({record['issue'] for record in with_issue})} issues of this repository"
        + (f"; {len(without)} have no issue here ({', '.join(without)})." if without else "."),
        f"Issues read: {sum(1 for issue in issues.values() if issue)}.",
        "",
    ]
    writes = [entry for entry in differences if any(entry[key] for key in ("add", "remove", "announce", "close"))]
    lines.append(f"Issues that differ from their record: {len(writes)}.")
    for entry in writes:
        what = (
            f"{', '.join(entry['findings'])}: {community.status_label(entry['stage'], provider)}"
            if entry["stage"]
            else "no merged record"
        )
        steps = []
        if entry["add"]:
            steps.append(f"add {names(entry['add'])}")
        if entry["remove"]:
            steps.append(f"remove {names(entry['remove'])}")
        if entry["announce"]:
            steps.append("comment once")
        if entry["close"]:
            steps.append(f"close as {entry['close'].replace('_', ' ')}")
        lines.append(f"{bullet}#{entry['issue']} ({what}): {'; '.join(steps)}")
    person = [text for entry in differences for text in entry["person"]]
    if person:
        lines += ["", f"For a person to decide: {len(person)}."] + [f"{bullet}{text}" for text in person]
    today = today or datetime.date.today()
    waiting = [
        (state["days"], record["id"], state)
        for record in findings
        if (state := community.staleness(record, today, config.get("stale_after_days"))) and state["stale"]
    ]
    if waiting:
        lines += ["", f"Waiting longer than the threshold of their status: {len(waiting)}."]
        for days, rid, state in sorted(waiting, key=lambda item: (-item[0], community.finding_number({"id": item[1]}))):
            lines.append(
                f"{bullet}{rid}: {community.status_label(state['status'], provider)} since {state['since']} "
                f"({days} days; threshold {state['threshold']})"
            )
    return "\n".join(lines) + "\n"


def main(argv=None, env=None, transport=None, out=print, pause=None):
    env = os.environ if env is None else env
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="write the differences; without it they are printed")
    parser.add_argument("--no-comments", action="store_true",
                        help="with --apply: write labels and state, post no comment (for a first, silent run)")
    parser.add_argument("--issues", type=Path, help="read the issues from a saved list instead of the network")
    parser.add_argument("--summary", type=Path, help="also append the report to this file, as Markdown")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    config = community.load_config(root)
    errors, _, _ = community.problems(root)
    if errors:
        out("The records are not valid; nothing was compared. Run `python3 scripts/community.py check`.")
        return 1
    repository = env.get("GITHUB_REPOSITORY") or repository_slug(config["repository"])
    if repository != repository_slug(config["repository"]):
        out(f"sync: {repository} is not the repository these records belong to; nothing done.")
        return 0
    if args.apply and args.issues:
        parser.error("--apply reads the issues from GitHub; leave --issues out")
    findings = community.load_findings(root)
    api = GitHub(repository, env.get("GITHUB_TOKEN"), transport=transport)
    try:
        issues = snapshot_issues(args.issues, findings) if args.issues else read_issues(api, findings)
    except RateLimited:
        out("sync: the rate limit is used up before the issues could be read; the next run goes on.")
        return 0
    except ApiError as error:
        out(f"sync: the issues could not be read: {error}")
        return 1
    differences = plan(findings, issues, config)
    text = report(differences, findings, issues, config)
    out(text, end="")
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as stream:
            stream.write(report(differences, findings, issues, config, markdown=True))
    if not args.apply:
        out("Nothing was written. `--apply` writes the labels, the comments and the state of the issues.")
        return 0
    try:
        done, left, stopped, failed = apply(differences, api, config["provider"], not args.no_comments, pause)
    except ApiError as error:
        out(f"sync: stopped by an error; what was written stays, and the next run goes on: {error}")
        return 1
    for number, error in failed:
        out(f"sync: issue #{number} could not be written; the others were: {error}")
    if stopped:
        # Not a failure: the nightly run takes up where this one stopped.
        out(f"::warning::sync stopped because {stopped}: {done} issues done, {left} left for the next run.")
    else:
        waiting = sum(len(entry["person"]) for entry in differences)
        out(f"sync: {done} issues brought into agreement with their records"
            + (f"; {waiting} points are left for a person." if waiting else "."))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
