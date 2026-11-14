"""From an issue to a finding record, and from a comment to a second measurement.

Standard library only. `.github/workflows/intake.yml` runs `intake.py run` and
`intake.py status`. What they do is decided by the functions below, which read no network:

    parse_form(body)                       the fields of an issue filed with the finding form
    record_from_issue(issue, config, ...)  a version 2 record with id F<issue number>, or why not
    command(comment_body)                  /repeated reproduced | /repeated not-reproduced | /record
    second_measurement(record, comment, ...)  the `repeated` block, or why it is refused
    plan(event_name, event, root)          what the workflow does for one event, as plain data
    publish(plan, api)                     carries a plan out through the GitHub API

Everything an issue or a comment says is untrusted:

- it is read from the event file as JSON and never put into a shell command;
- it reaches a record only through the form's fields, with a length limit on each, and the
  record must pass `community.validate_finding`, which refuses raw HTML;
- it is never printed to the job log (a runner reads commands from what a step prints), and
  never copied into a comment, a commit message or a pull request text: those are written
  here, word for word;
- it reaches the site only after a person has merged the pull request.

The headings of the form are a contract with the issues already filed. To rename a heading,
move the old one to EARLIER_FORM; `community/tests/test_intake.py` compares FORM with
the issue form that `finding_form` in site/config.json names.
"""

import argparse
import base64
import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import community  # noqa: E402
from github_api import ApiError, GitHub, NotFound, plain, repository_slug  # noqa: E402

ROOT = community.ROOT
# What this repository calls its form and its label, and whose data it is about: site/config.json.
NAMES = community.load_config()
PROVIDER = NAMES["provider"]
FORM_FILE = f".github/ISSUE_TEMPLATE/{NAMES['finding_form']}"
FINDING_LABEL = NAMES["finding_label"]
NEEDS_INFO = "needs-info"
TITLE_PREFIX = re.compile(r"\A\s*\[finding\]\s*", re.I)

# The form: (field id, the heading GitHub writes for it, required).
FORM = (
    ("kind", "What kind of finding is it?", True),
    ("releases", f"{PROVIDER} release it was observed in", True),
    ("datasets", "Datasets, one per line", False),
    ("scope", "What else it concerns", False),
    ("observation", "What the data says", True),
    ("method", "How you measured it", True),
    ("exposure", "What it affects, if known", False),
    ("notes", "Anything else", False),
)
# The form as it was until November 2026. Issues filed with it stay readable.
EARLIER_FORM = (
    ("dataset", f"{PROVIDER} activity code(s), name, geography, unit", True),
    ("release", "Release observed in", True),
    ("where", "Where you looked", True),
    ("measured", "What you measured, and how", True),
    ("why", "Why it cannot be right", True),
    ("exposure", "Exposure, if known", False),
    ("correction", "Suggested correction (optional)", False),
)
FORMS = {2: FORM, 1: EARLIER_FORM}
HEADINGS = {heading: (version, field) for version, form in FORMS.items() for field, heading, _ in form}
HEADING_OF = {field: heading for field, heading, _ in FORM}
EARLIER_HEADING_OF = {field: heading for field, heading, _ in EARLIER_FORM}
# What the earlier form called "both": the two releases it offered.
EARLIER_BOTH = ("2025-v2", "2026-v1")

# Longer than this, a field is refused, never cut: a cut text says something else.
LIMITS = {"title": 300, "scope": 500, "observation": 20000, "method": 10000, "exposure": 5000, "notes": 5000}
MAX_BODY = 65536  # what GitHub accepts as an issue body
MAX_DATASETS = 200
NO_RESPONSE = {"_No response_", "None"}
FENCED = re.compile(r"\A```[A-Za-z]*\n(.*)\n```\Z", re.S)  # how a `render: text` field arrives
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
ONE_LINE = re.compile(r"[|\r\n\u000b\u000c\u001c-\u001e\u0085\u2028\u2029]")
LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})(?:\[bot\])?")
SHA = re.compile(r"[0-9a-f]{40}")
BRANCH = re.compile(r"[A-Za-z0-9._/-]+")
MAINTAINERS = {"OWNER", "MEMBER", "COLLABORATOR"}
# The job names of .github/workflows/checks.yml, read from that file: each repository has its
# own jobs. A pull request opened by a workflow starts no workflow, so intake.yml runs the same
# checks and reports them under the same names.
CHECKS_FILE = ".github/workflows/checks.yml"


def check_contexts(root=ROOT):
    """The name of every job of the checks workflow, in its order; none where there is no file."""
    path = Path(root) / CHECKS_FILE
    if not path.is_file():
        return ()
    jobs = path.read_text(encoding="utf-8").split("\njobs:\n", 1)[-1]
    return tuple(name.strip().strip("\"'") for name in re.findall(r"(?m)^    name: (.+)$", jobs))


CHECK_CONTEXTS = check_contexts()

# The fields of a record that come from the form; `/record` replaces these and nothing else.
FORM_FIELDS = ("title", "kind", "datasets", "scope", "releases", "observation", "exposure", "method", "notes")


# ------------------------------------------------------------------------------------ form


def parse_form(body):
    """The fields of an issue body filed with the finding form.

    {"version": 2 or 1, "fields": {id: text}, "problems": [...]}. `version` is None when the
    body has none of the form's headings: it was not filed with the form. `problems` says
    what is wrong with a body that has some of them.
    """
    text = CONTROL.sub("", (body or "").replace("\r\n", "\n").replace("\r", "\n"))
    sections, order, current, preamble = {}, [], None, []
    duplicates = []
    for line in text.split("\n"):
        match = re.fullmatch(r"###[ \t]+(.+?)[ \t]*", line)
        heading = match.group(1) if match else None
        if heading in HEADINGS:
            if heading in sections:
                duplicates.append(heading)
            current = heading
            sections[heading] = []
            order.append(heading)
        elif current is None:
            preamble.append(line)
        else:
            sections[current].append(line)
    versions = {HEADINGS[heading][0] for heading in order}
    if not versions:
        return {"version": None, "fields": {}, "problems": []}
    problems = []
    if len(versions) > 1:
        return {
            "version": None,
            "fields": {},
            "problems": ["The issue mixes the headings of the form with those of the earlier form."],
        }
    version = versions.pop()
    for heading in dict.fromkeys(duplicates):
        problems.append(f'The heading "{heading}" appears twice.')
    if "".join(preamble).strip():
        problems.append("There is text before the first heading of the form.")
    fields = {}
    for field, heading, required in FORMS[version]:
        if heading not in sections:
            if required:
                problems.append(f'The heading "{heading}" is missing.')
            fields[field] = ""
            continue
        value = "\n".join(sections[heading]).strip()
        fenced = FENCED.match(value)
        if fenced:
            value = fenced.group(1).strip("\n")
        fields[field] = "" if value in NO_RESPONSE else value
    return {"version": version, "fields": fields, "problems": problems}


def release_ids(text, config, strict):
    """The registered releases a form value names: by id, or by name."""
    known = {}
    for release in config["releases"]:
        known[release["id"].lower()] = release["id"]
        known[release["name"].lower()] = release["id"]
    registered = [r["id"] for r in config["releases"]]
    if strict:
        items = [item.strip().lower() for item in text.split(",") if item.strip()]
        if not items or any(item not in known for item in items):
            return None
        found = {known[item] for item in items}
    else:
        lowered = text.lower()
        found = {rid for name, rid in known.items() if name in lowered}
        if lowered.strip() == "both":
            found = set(EARLIER_BOTH) & set(registered)
    return [rid for rid in registered if rid in found] or None


def dataset_lines(text, known):
    """The datasets of the form's list: (datasets, problems, notes). One per line,
    `number | name | location`; a number alone is enough when another record lists the dataset."""
    heading = HEADING_OF["datasets"]
    datasets, problems, notes, seen = [], [], [], set()
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if len(lines) > MAX_DATASETS:
        return [], [f'"{heading}" lists more than {MAX_DATASETS} datasets. Name the group under '
                    f'"{HEADING_OF["scope"]}" instead.'], []
    for number, line in enumerate(lines, start=1):
        parts = [part.strip() for part in line.split("|")]
        code = parts[0]
        if not re.fullmatch(r"[1-9][0-9]{0,11}", code) or len(parts) not in (1, 3) or (
            len(parts) == 3 and not (parts[1] and parts[2])
        ):
            problems.append(
                f'"{heading}", line {number}: write the dataset number, its name and its location, '
                "separated by bars, for example: 191385 | Refrigerant R134a, at plant | RER"
            )
            continue
        code = int(code)
        if code in seen:
            problems.append(f'"{heading}", line {number}: dataset {code} is listed twice.')
            continue
        seen.add(code)
        if code in known:
            # One name per dataset number across all records: the records that exist decide.
            entry = {"code": code, "name": known[code]["name"], "location": known[code]["location"]}
            if len(parts) == 3 and (parts[1], parts[2]) != (entry["name"], entry["location"]):
                notes.append(f"Dataset {code}: name and location are taken from the records that already list it.")
        elif len(parts) == 3:
            entry = {"code": code, "name": parts[1], "location": parts[2]}
        else:
            problems.append(
                f'"{heading}", line {number}: no record lists dataset {code} yet, so give its name and '
                f"location too: {code} | name | location"
            )
            continue
        datasets.append(entry)
    return datasets, problems, notes


def text_problems(name, text, limit, one_line=False):
    """What a record would refuse in one field of the form, in the reporter's words.
    `name` is how the field is called in the message: the title, or a heading in quotes."""
    problems = []
    if len(text) > limit:
        problems.append(f"{name} is longer than {limit:,} characters. Shorten it and link to the full material.")
    if community.RAW_HTML.search(text):
        problems.append(
            f'{name} holds raw HTML (a "<" followed by a letter, "/" or "!"). Records hold '
            'Markdown only: write the tag in words, or put a space after the "<".'
        )
    if one_line:
        if ONE_LINE.search(text):
            problems.append(f'{name} must be one line without a bar ("|").')
        return problems
    wording = {
        "has a link that is not a full https address": "has a link that is not a full https address.",
        "embeds an image; link to it instead": "embeds an image. Link to it instead.",
        "has a heading; the page sets the headings": 'has a line that starts with "#". Records hold no headings.',
        "defines a link apart from its text; write [text](https://…)":
            "defines a link apart from its text. Write [text](https://…).",
    }
    for error in community.markdown_errors({"": text}):
        problems.append(f"{name} {wording.get(error.strip(), 'is not plain Markdown.')}")
    return problems


def record_from_issue(issue, config, known=None):
    """A version 2 record from an issue filed with the form.

    {"result": "record", "record": {...}, "notes": [...]}; the record has the id F<issue
    number>, `reported` filled from the issue, and no other evidence, so its status is
    "Needs a second measurement".
    {"result": "not-form"} when the issue was not filed with the form.
    {"result": "incomplete", "problems": [...]} with what the reporter can put right.
    `known` is `community.dataset_index` of the records that exist.
    """
    known = known or {}
    body = issue.get("body") or ""
    if len(body) > MAX_BODY:
        return {"result": "incomplete", "problems": [f"The issue text is longer than {MAX_BODY:,} characters."]}
    form = parse_form(body)
    if form["version"] is None and not form["problems"]:
        return {"result": "not-form"}
    problems, notes = list(form["problems"]), []
    fields, version = form["fields"], form["version"]
    if version is None:
        return {"result": "incomplete", "problems": problems}
    for field, heading, required in FORMS[version]:
        if required and not fields.get(field):
            problems.append(f'"{heading}" is empty.')
    number = issue.get("number")
    login = (issue.get("user") or {}).get("login") or ""
    created = str(issue.get("created_at") or "")[:10]
    if not (isinstance(number, int) and not isinstance(number, bool) and number > 0):
        return {"result": "incomplete", "problems": ["The issue has no number."]}
    if not LOGIN.fullmatch(login) or not community.real_date(created):
        return {"result": "incomplete", "problems": ["The issue does not say who filed it and when."]}

    title = re.sub(r"\s+", " ", TITLE_PREFIX.sub("", CONTROL.sub("", issue.get("title") or ""))).strip()
    if not title:
        problems.append("The title is empty. Say in one line what was observed.")
    problems += text_problems("The title", title, LIMITS["title"], one_line=True)

    provider = config["provider"]
    if version == 2:
        kind = fields["kind"].split(":", 1)[0].strip().lower()
        if fields["kind"] and kind not in community.KINDS:
            problems.append(f'"{HEADING_OF["kind"]}": choose one of the options of the form.')
        releases = release_ids(fields["releases"], config, strict=True) if fields["releases"] else None
        if fields["releases"] and releases is None:
            problems.append(
                f'"{HEADING_OF["releases"]}": choose from the form\'s list ('
                + ", ".join(r["id"] for r in config["releases"]) + ")."
            )
        datasets, found, more = dataset_lines(fields["datasets"], known)
        problems += found
        notes += more
        texts = {key: fields[key] for key in ("scope", "observation", "method", "exposure", "notes")}
        if not datasets and not found and not texts["scope"]:
            problems.append(f'Name at least one dataset, or say under "{HEADING_OF["scope"]}" what the finding concerns.')
        named = {key: f'"{HEADING_OF[key]}"' for key in texts}
    else:
        kind = "defect"
        notes.append("Filed with the earlier form, which did not ask for the kind: set to defect.")
        releases = release_ids(fields["release"], config, strict=False) if fields["release"] else None
        if fields["release"] and releases is None:
            problems.append(
                f'"{EARLIER_HEADING_OF["release"]}": name a registered release ('
                + ", ".join(r["name"] for r in config["releases"]) + ")."
            )
        datasets = []
        notes.append(
            "Filed with the earlier form, which asked for the datasets in one free line: that line is "
            "in `scope`. List the datasets in `datasets` before merging."
        )
        measured = fields["measured"]
        # The earlier form kept this field as plain text; a fence keeps its columns.
        fenced = f"```text\n{measured}\n```" if "\n" in measured else measured
        # The earlier form's release field took free text; what it says beyond the name is kept.
        stated = fields["release"]
        exact = stated.lower() in {r["name"].lower() for r in config["releases"]} | {"both"}
        where = fields["where"] if exact or not stated else f"{fields['where']}\n\nRelease, as the issue states it: {stated}"
        texts = {
            "scope": fields["dataset"],
            "observation": "\n\n".join(part for part in (fenced, fields["why"]) if part),
            "method": where,
            "exposure": fields["exposure"],
            "notes": f"Suggested correction: {fields['correction']}" if fields["correction"] else "",
        }
        came_from = {"scope": "dataset", "observation": "measured", "method": "where",
                     "exposure": "exposure", "notes": "correction"}
        named = {key: f'"{EARLIER_HEADING_OF[field]}"' for key, field in came_from.items()}
    for key, text in texts.items():
        problems += text_problems(named[key], text, LIMITS[key], one_line=key == "scope")
    if problems:
        return {"result": "incomplete", "problems": list(dict.fromkeys(problems))}

    url = f"{config['repository']}/issues/{number}"
    record = {
        "schema": 2,
        "id": f"F{number}",
        "issue": number,
        "title": title,
        "kind": kind,
        "datasets": datasets,
        "scope": texts["scope"],
        "releases": releases,
        "observation": texts["observation"],
        "exposure": texts["exposure"],
        "method": texts["method"],
        "reported": {"by": login, "date": created, "url": url},
        "repeated": None,
        "sent": None,
        "answer": None,
        "fixed_in": None,
        "closed": None,
        "related": [],
        "threads": [],
        "next": {
            "action": f"A second person repeats the measurement on {provider}'s release files. "
                      f"Then the finding is reported to {provider}.",
            "role": "reviewer",
        },
        "retained": [],
        "notes": texts["notes"],
    }
    errors = community.validate_finding(
        record, community.record_path(record), {r["id"] for r in config["releases"]}, config["older_numbering_until"]
    )
    if errors:
        return {
            "result": "incomplete",
            "problems": ["The record made from this issue does not pass the checks: "
                         + "; ".join(plain(error) for error in errors[:5])],
        }
    return {"result": "record", "record": record, "notes": notes}


# -------------------------------------------------------------------------------- comments


def command(body):
    """The command a comment begins with, or None.

    ("repeated", "reproduced" | "not-reproduced", "F48" | None), ("repeated", None, None) when
    the line begins with /repeated and says nothing this script understands, ("record", None,
    None). The command is the first line of the comment and nothing else on that line.
    """
    first = (body or "").replace("\r", "\n").split("\n", 1)[0].rstrip()
    if first == "/record":
        return ("record", None, None)
    if not re.match(r"/repeated(?![A-Za-z0-9_-])", first):
        return None
    match = re.fullmatch(r"/repeated[ \t]+(reproduced|not-reproduced)(?:[ \t]+(F[1-9][0-9]*))?", first)
    return ("repeated", match.group(1), match.group(2)) if match else ("repeated", None, None)


def second_measurement(record, comment, issue_number, repository, result):
    """The `repeated` block a /repeated comment gives a record, or why it is refused.

    {"result": "repeated", "record": the record with the block} or {"result": "refused",
    "why": "reporter" | "no-reporter" | "already" | "closed" | "invalid"}.
    """
    user = comment.get("user") or {}
    login, date, cid = user.get("login") or "", str(comment.get("created_at") or "")[:10], comment.get("id")
    reporter = (record.get("reported") or {}).get("by")
    if not reporter:
        return {"result": "refused", "why": "no-reporter"}
    if not LOGIN.fullmatch(login) or not isinstance(cid, int) or isinstance(cid, bool):
        return {"result": "refused", "why": "invalid"}
    if community.same_person(login, reporter):
        return {"result": "refused", "why": "reporter"}
    if record.get("closed"):
        return {"result": "refused", "why": "closed"}
    if record.get("repeated"):
        return {"result": "refused", "why": "already"}
    changed = dict(record)
    changed["repeated"] = {
        "by": login,
        "date": date,
        "url": f"{repository}/issues/{issue_number}#issuecomment-{cid}",
        "result": result,
    }
    return {"result": "repeated", "record": changed}


# ------------------------------------------------------------------------------------ plan

FORM_URL = "{repository}/issues/new?template=" + NAMES["finding_form"]
REPLIES = {
    "not-form": (
        f"This issue carries the label `{FINDING_LABEL}`, but it was not filed with the finding form, so "
        "no record can be made from it automatically. Please [file it with the form]({form}); a "
        "maintainer can also write the record by hand."
    ),
    "legacy": (
        "This issue is older than the automatic numbering of findings (it began with issue "
        "{first}), so no record is proposed automatically. A maintainer writes the record by hand."
    ),
    "recorded": (
        "This finding is already recorded as **{finding}**, so an edit of the issue does not change "
        "its record. To change the record, a maintainer comments `/record` here (the edited form is "
        "then proposed as a pull request), or anyone opens a pull request on "
        "[its file]({repository}/blob/{base}/{path})."
    ),
    "unchanged": "The record of **{finding}** already says what this issue says; there is nothing to propose.",
    "maintainer": (
        "`/record` asks for the record to be proposed from the issue again. Only a maintainer of this "
        "repository can ask for that."
    ),
    "not-finding": (
        f"This issue does not carry the label `{FINDING_LABEL}`. A maintainer adds the label and "
        "comments `/record` again."
    ),
    "usage": (
        "To record a second measurement, begin a comment with one of these lines and say below it "
        "what you measured and got:\n\n```\n/repeated reproduced\n/repeated not-reproduced\n```"
    ),
    "no-record": (
        "This finding has no merged record yet, so a second measurement cannot be recorded. Once a "
        "maintainer has merged the record, comment again with `/repeated reproduced` or "
        "`/repeated not-reproduced`. What you measured is welcome here in the meantime."
    ),
    "which": (
        "This issue holds more than one finding ({findings}). Name the one you measured, for example "
        "`/repeated reproduced {example}`."
    ),
    "other-issue": "{finding} is not discussed in this issue. Comment in the issue of that finding.",
    "reporter": (
        "Thank you for measuring again. A second measurement has to come from someone other than "
        "the person who reported the finding, so this one is not recorded. Your result is still "
        "useful here in the discussion."
    ),
    "no-reporter": (
        "The record of **{finding}** does not name who reported it, so a second person cannot be told "
        "apart. A maintainer records your measurement by hand."
    ),
    "already": (
        "A second measurement of **{finding}** is already recorded. Further measurements are welcome "
        "in this discussion; a maintainer can replace the recorded one "
        "(`python3 scripts/community.py repeat {finding} --replace …`)."
    ),
    "closed": "**{finding}** is closed, so a second measurement is not recorded. Your result is still useful here.",
    "invalid": "This comment could not be read as a second measurement. A maintainer records it by hand.",
    "pending": (
        "A second measurement of **{finding}** is already proposed in {pull}, and a maintainer decides "
        "there. Yours is welcome here in the discussion."
    ),
    "by-hand": (
        "The record proposed in {pull} was changed by hand after it was proposed, so the edit of this "
        "issue is not copied into it. A maintainer brings the two together in that pull request."
    ),
    "proposed": (
        "Thank you. This report is finding **{finding}**. Its record is proposed in {pull}; a maintainer "
        "reads it before it is merged.\n\n"
        "What happens next:\n\n"
        "1. Once the record is merged, the finding is listed on the [site]({site}) with the status "
        "\"{filed}\".\n"
        "2. A second person repeats the measurement on {provider}'s release files and comments here, "
        "beginning with the line `/repeated reproduced` or `/repeated not-reproduced`.\n"
        "3. Findings are reported to {provider} together. {provider} decides what it changes; its "
        "answer is recorded here.\n\n"
        "If you edit the issue before the record is merged, the proposed record follows."
    ),
    "reproposed": "The record of **{finding}** is proposed from this issue again in {pull}.",
    "repeated": (
        "Thank you. Your measurement is proposed for the record of **{finding}** in {pull}. A "
        "maintainer reads your comment before it is merged."
    ),
}
PULL_BODY = {
    "new": (
        "Proposes the record of finding {finding} from the form of #{issue}. Written by the intake "
        "workflow; nobody has reviewed it yet.\n\n"
        "Before merging, a maintainer checks:\n\n"
        "- Is it a finding: a measured observation about {provider}'s data?\n"
        "- Names, numbers and single values only. No text pasted from {provider}'s reports.\n"
        "- Are the dataset numbers, names and locations right, and does the kind fit?\n\n"
        "{notes}"
        "This pull request adds one file. After the merge the finding is listed with the status "
        "\"{filed}\", and the labels of #{issue} follow the record."
    ),
    "update": (
        "Proposes the record of finding {finding} again from the form of #{issue}, because a "
        "maintainer asked for it with `/record`. Only the fields that come from the form change; "
        "the evidence in the record is kept.\n\n"
        "Before merging, a maintainer reads the difference: it replaces what was written by hand "
        "in those fields.\n\n{notes}"
    ),
    "repeat": (
        "Records a second measurement of finding {finding}: {result}, as said in "
        "[this comment]({url}) on #{issue}.\n\n"
        "Before merging, a maintainer reads the comment:\n\n"
        "- Does it say what was measured, on {provider}'s release files, and what came out?\n"
        "- Is it by a second person, not by the reporter under another name?\n\n"
        "This pull request changes one file. After the merge the status of the finding follows "
        "from the record, and so do the labels of #{issue}."
    ),
}


def nothing(why, issue=None):
    return {"action": "nothing", "why": why, "issue": issue}


def reply(why, issue, marker, add_labels=(), **values):
    return {
        "action": "reply",
        "why": why,
        "issue": issue,
        "marker": marker,
        "comment": REPLIES[why].format(**values),
        "add_labels": list(add_labels),
    }


def record_text(record):
    """A record as the text of its file: the fields in their fixed order, as every record is written."""
    ordered = {key: record[key] for key in community.FINDING_FIELDS if key in record}
    return json.dumps(ordered, indent=2, ensure_ascii=False) + "\n"


def tree_errors(record, others, patches, releases, older_until=None):
    """What the check of the whole tree would say with this record in it."""
    errors = community.validate_finding(record, community.record_path(record), releases, older_until)
    if not errors:
        rest = [other for other in others if other["id"] != record["id"]]
        errors, _ = community.cross_record_errors(rest + [record], patches)
    return errors


def plan(event_name, event, root=ROOT):
    """What the workflow does for one event: plain data, no network, nothing written.

    {"action": "nothing" | "reply" | "write", "why": a fixed word, "issue": n, ...}. A reply
    carries the comment and its marker (posted once); a write carries the branch, the path,
    the text of the record file and the texts of the commit, the pull request and the reply.
    """
    root = Path(root)
    config = community.load_config(root)
    repository, provider = config["repository"], config["provider"]
    issue = event.get("issue") or {}
    number = issue.get("number")
    if not isinstance(number, int) or isinstance(number, bool) or number < 1:
        return nothing("no-issue")
    if "pull_request" in issue:
        return nothing("pull-request", number)
    labels = {label.get("name") for label in issue.get("labels") or [] if isinstance(label, dict)}
    findings = community.load_findings(root)
    here = [record for record in findings if record.get("issue") == number]
    base = (event.get("repository") or {}).get("default_branch") or "main"
    values = dict(
        repository=repository,
        form=FORM_URL.format(repository=repository),
        site=config["site_url"],
        provider=provider,
        filed=community.status_label("filed", provider),
        first=config["older_numbering_until"] + 1,
        base=base,
    )

    forced = False
    if event_name == "issues":
        if event.get("action") not in ("opened", "edited"):
            return nothing("not-opened-or-edited", number)
        if FINDING_LABEL not in labels:
            return nothing("not-a-finding", number)
        if here:
            if event.get("action") == "opened":
                return nothing("recorded", number)
            first = here[0]
            return reply("recorded", number, "intake: recorded", finding=first["id"], path=first.path, **values)
    elif event_name == "issue_comment":
        comment = event.get("comment") or {}
        if event.get("action") != "created":
            return nothing("not-created", number)
        if (comment.get("user") or {}).get("type") == "Bot":
            return nothing("bot", number)
        asked = command(comment.get("body"))
        if asked is None:
            return nothing("no-command", number)
        cid = comment.get("id")
        if not isinstance(cid, int) or isinstance(cid, bool):
            return nothing("no-comment-id", number)
        marker = f"intake: reply {cid}"
        if asked[0] == "repeated":
            return plan_repeat(asked, comment, number, here, findings, root, config, marker, values)
        if comment.get("author_association") not in MAINTAINERS:
            return reply("maintainer", number, marker, **values)
        if FINDING_LABEL not in labels:
            return reply("not-finding", number, marker, **values)
        forced = True
    else:
        return nothing("other-event", number)

    outcome = record_from_issue(issue, config, community.dataset_index(findings))
    if outcome["result"] == "not-form":
        return reply("not-form", number, "intake: not-form", [NEEDS_INFO], **values)
    if outcome["result"] == "incomplete":
        problems = outcome["problems"]
        digest = hashlib.sha256("\n".join(problems).encode()).hexdigest()[:12]
        return {
            "action": "reply",
            "why": "incomplete",
            "issue": number,
            "marker": f"intake: needs-info {digest}",
            "comment": "No record could be made from this issue yet:\n\n"
            + "".join(f"- {problem}\n" for problem in problems)
            + "\nPlease edit the issue. The record is proposed as soon as the form is complete.",
            "add_labels": [NEEDS_INFO],
            "problems": problems,
        }
    record, notes = outcome["record"], outcome["notes"]
    kind = "new"
    if here:
        # /record on a finding that has a record: the form's fields again, the evidence kept.
        if len(here) > 1:
            return reply("which", number, f"intake: reply {event['comment']['id']}",
                         findings=", ".join(r["id"] for r in here), example=here[0]["id"], **values)
        existing = dict(here[0])
        merged = dict(existing, **{key: record[key] for key in FORM_FIELDS})
        if merged == existing:
            return reply("unchanged", number, f"intake: reply {event['comment']['id']}", finding=existing["id"], **values)
        record, kind = merged, "update"
    elif number <= config["older_numbering_until"]:
        return reply("legacy", number, "intake: legacy", **values)
    releases = {r["id"] for r in config["releases"]}
    errors = tree_errors(record, findings, community.load_patches(root), releases, config["older_numbering_until"])
    if errors:
        problems = ["The record made from this issue does not pass the checks: "
                    + "; ".join(plain(error) for error in errors[:5])]
        digest = hashlib.sha256("\n".join(problems).encode()).hexdigest()[:12]
        return {
            "action": "reply", "why": "incomplete", "issue": number,
            "marker": f"intake: needs-info {digest}",
            "comment": "No record could be made from this issue yet:\n\n"
            + "".join(f"- {problem}\n" for problem in problems)
            + "\nPlease edit the issue. The record is proposed as soon as the form is complete.",
            "add_labels": [NEEDS_INFO], "problems": problems,
        }
    rid = record["id"]
    noted = "".join(f"- {note}\n" for note in notes)
    body = PULL_BODY[kind].format(
        finding=rid, issue=number, notes=f"Notes from the intake:\n\n{noted}\n" if noted else "", **values
    )
    return {
        "action": "write",
        "why": "propose" if kind == "new" else "repropose",
        "kind": kind,
        "forced": forced,
        "issue": number,
        "finding": rid,
        "base": base,
        "branch": f"intake/{rid}",
        "path": community.record_path(record),
        "content": record_text(record),
        "commit": f"findings: propose {rid} from issue #{number}\n\n"
                  "Written by the intake workflow from the issue form. A person reviews and merges.",
        "title": f"findings: propose {rid} from issue #{number}",
        "body": body,
        "marker": f"intake: proposed {rid}" if kind == "new" else f"intake: reply {event['comment']['id']}",
        "comment": REPLIES["proposed" if kind == "new" else "reproposed"].format(finding=rid, pull="{pull}", **values),
        "remove_labels": [NEEDS_INFO] if NEEDS_INFO in labels else [],
        "notes": notes,
    }


def plan_repeat(asked, comment, number, here, findings, root, config, marker, values):
    _, result, named = asked
    if result is None:
        return reply("usage", number, marker, **values)
    if not here:
        return reply("no-record", number, marker, **values)
    if named:
        chosen = [record for record in here if record["id"] == named]
        if not chosen:
            return reply("other-issue", number, marker, finding=named, **values)
    elif len(here) > 1:
        return reply("which", number, marker, findings=", ".join(r["id"] for r in here), example=here[0]["id"], **values)
    else:
        chosen = here
    record = chosen[0]
    rid = record["id"]
    outcome = second_measurement(dict(record), comment, number, config["repository"], result)
    if outcome["result"] == "refused":
        return reply(outcome["why"], number, marker, finding=rid, **values)
    changed = outcome["record"]
    releases = {r["id"] for r in config["releases"]}
    if tree_errors(changed, findings, community.load_patches(root), releases, config["older_numbering_until"]):
        return reply("invalid", number, marker, finding=rid, **values)
    url = changed["repeated"]["url"]
    words = {"reproduced": "reproduced", "not-reproduced": "not reproduced"}[result]
    return {
        "action": "write",
        "why": "repeat",
        "kind": "repeat",
        "forced": True,
        "issue": number,
        "finding": rid,
        "base": values["base"],
        "branch": f"repeat/{rid}",
        "path": record.path,
        "content": record_text(changed),
        "commit": f"findings: record the second measurement of {rid} ({words})\n\n"
                  f"From a comment on issue #{number}. A person reads the comment and merges.",
        "title": f"findings: record the second measurement of {rid} ({words})",
        "body": PULL_BODY["repeat"].format(finding=rid, issue=number, result=words, url=url, **values),
        "marker": marker,
        "comment": REPLIES["repeated"].format(finding=rid, pull="{pull}", **values),
        "remove_labels": [],
        "notes": [],
    }


# --------------------------------------------------------------------------------- publish


def file_on(api, path, branch):
    """(blob sha, text) of a file on a branch, or None."""
    try:
        found = api.get(f"/contents/{path}?ref={branch}")
    except NotFound:
        return None
    if not isinstance(found, dict) or found.get("encoding") != "base64":
        raise ApiError("GET", f"/contents/{path}", 200, "not a file")
    return found["sha"], base64.b64decode(found["content"]).decode()


def publish(plan, api):
    """Carry a plan out. {"done": a fixed word, "sha": the commit to check or None, "ref": its
    branch, "pull": the pull request number}. Every step can be repeated: a second run of the
    same event writes nothing new."""
    done = {"done": plan["action"], "why": plan["why"], "sha": None, "ref": None, "pull": None}
    issue = plan.get("issue")
    if plan["action"] == "nothing":
        return done
    if plan["action"] == "reply":
        done["posted"] = api.comment_once(issue, plan["marker"], plan["comment"])
        if plan["add_labels"]:
            api.post(f"/issues/{issue}/labels", {"labels": plan["add_labels"]})
        return done

    branch, path, base, content = plan["branch"], plan["path"], plan["base"], plan["content"]
    if not (BRANCH.fullmatch(branch) and BRANCH.fullmatch(base) and BRANCH.fullmatch(path)):
        raise ValueError("a branch or a path does not have the expected form")
    owner = api.repository.split("/")[0]
    pulls = api.get(f"/pulls?head={owner}:{branch}&state=all&per_page=100") or []
    opened = next((pull for pull in pulls if pull.get("state") == "open"), None)
    values = dict(finding=plan["finding"])
    if not opened and pulls and plan["kind"] == "new" and not plan["forced"]:
        # A maintainer closed the proposal. An edit of the issue does not bring it back.
        return dict(done, done="nothing", why="closed-before")
    head = api.get(f"/git/ref/heads/{base}")["object"]["sha"]
    payload = {"message": plan["commit"], "content": base64.b64encode(content.encode()).decode(), "branch": branch}
    if opened:
        pull = opened["number"]
        current = file_on(api, path, branch)
        if current and current[1] == content:
            sha = api.get(f"/git/ref/heads/{branch}")["object"]["sha"]
            return dict(done, done="unchanged", sha=sha, ref=branch, pull=pull)
        if plan["kind"] == "repeat":
            api.comment_once(issue, plan["marker"], REPLIES["pending"].format(pull=f"#{pull}", **values))
            return dict(done, done="reply", why="pending", pull=pull)
        last = api.get(f"/commits?sha={branch}&path={path}&per_page=1") or []
        if last and (last[0].get("author") or {}).get("type") != "Bot":
            api.comment_once(issue, f"intake: by-hand {pull}", REPLIES["by-hand"].format(pull=f"#{pull}", **values))
            return dict(done, done="reply", why="by-hand", pull=pull)
        if current:
            payload["sha"] = current[0]
        sha = api.put(f"/contents/{path}", payload)["commit"]["sha"]
    else:
        try:
            api.get(f"/git/ref/heads/{branch}")
            api.patch(f"/git/refs/heads/{branch}", {"sha": head, "force": True})
        except NotFound:
            api.post("/git/refs", {"ref": f"refs/heads/{branch}", "sha": head})
        current = file_on(api, path, branch)
        if current and current[1] == content:
            return dict(done, done="nothing", why="already-on-base")
        if current:
            payload["sha"] = current[0]
        sha = api.put(f"/contents/{path}", payload)["commit"]["sha"]
        pull = api.post("/pulls", {"title": plan["title"], "head": branch, "base": base, "body": plan["body"]})["number"]
    if not SHA.fullmatch(str(sha)) or not isinstance(pull, int):
        raise ApiError("PUT", f"/contents/{path}", 200, "no commit")
    api.comment_once(issue, plan["marker"], plan["comment"].replace("{pull}", f"#{pull}"))
    for label in plan["remove_labels"]:
        try:
            api.delete(f"/issues/{issue}/labels/{label}")
        except NotFound:
            pass
    return dict(done, done="written", sha=sha, ref=branch, pull=pull)


def post_statuses(api, sha, result, target=None):
    """Report the checks of a proposed commit under the names a pull request's own checks have."""
    if not SHA.fullmatch(sha or ""):
        raise ValueError("not a commit")
    passed = result == "success"
    for context in CHECK_CONTEXTS:
        body = {
            "state": "success" if passed else "failure",
            "context": context,
            "description": ("Passed" if passed else "Did not pass") + ", run by the intake workflow on this commit.",
        }
        if target:
            body["target_url"] = target
        api.post(f"/statuses/{sha}", body)
    return passed


# ------------------------------------------------------------------------------------ form file

RELEASE_BLOCK = re.compile(r"(?ms)^(?P<indent>[ \t]*)# releases:start[^\n]*\n.*?^[ \t]*# releases:end[^\n]*\n")


def form_with_releases(text, config):
    """The form file with its release list written from site/config.json, newest first."""

    def block(match):
        indent = match.group("indent")
        lines = [f"{indent}# releases:start (written by `python3 scripts/intake.py form` from site/config.json)"]
        lines.append(f"{indent}options:")
        lines += [f'{indent}  - "{release["id"]}"' for release in reversed(config["releases"])]
        lines.append(f"{indent}# releases:end")
        return "\n".join(lines) + "\n"

    changed, count = RELEASE_BLOCK.subn(block, text)
    if count != 1:
        raise ValueError(f"{FORM_FILE} needs exactly one block between '# releases:start' and '# releases:end'")
    return changed


# ------------------------------------------------------------------------------------- main


def environment(env):
    """The repository, the event and its name, as the runner gives them."""
    with open(env["GITHUB_EVENT_PATH"], encoding="utf-8") as stream:
        event = json.load(stream)
    return env["GITHUB_REPOSITORY"], env["GITHUB_EVENT_NAME"], event


def append(path, text):
    if path:
        with open(path, "a", encoding="utf-8") as stream:
            stream.write(text)


def run(env, root=ROOT, transport=None):
    """One event, from the event file to the pull request. Prints fixed words only."""
    repository, name, event = environment(env)
    if repository_slug(community.load_config(root)["repository"]) != repository:
        print(f"intake: {repository} is not the repository these records belong to; nothing done.")
        return 0
    planned = plan(name, event, root)
    api = GitHub(repository, env.get("GITHUB_TOKEN"), transport=transport)
    done = publish(planned, api)
    issue = planned.get("issue")
    line = f"intake: issue #{issue}: {done['done']} ({done['why']})"
    if done.get("pull"):
        line += f", pull request #{done['pull']}"
    print(line)
    if done["sha"]:
        append(env.get("GITHUB_OUTPUT"), f"sha={done['sha']}\nref={done['ref']}\n")
    append(env.get("GITHUB_STEP_SUMMARY"), f"{line}\n")
    return 0


def status(env, root=ROOT, transport=None):
    """Report the result of the checks on the proposed commit."""
    repository = env["GITHUB_REPOSITORY"]
    sha, result = env.get("INTAKE_SHA", ""), env.get("INTAKE_CHECKS", "")
    target = None
    server, run_id = env.get("GITHUB_SERVER_URL", ""), env.get("GITHUB_RUN_ID", "")
    if re.fullmatch(r"https://[A-Za-z0-9.-]+", server) and run_id.isdigit():
        target = f"{server}/{repository}/actions/runs/{run_id}"
    api = GitHub(repository, env.get("GITHUB_TOKEN"), transport=transport)
    passed = post_statuses(api, sha, result, target)
    print(f"intake: checks {'passed' if passed else 'did not pass'} on {sha[:12]}")
    return 0


def main(argv=None, env=None):
    env = os.environ if env is None else env
    top = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    top.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    sub = top.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="for the workflow: read the event, propose the record, answer on the issue")
    sub.add_parser("status", help="for the workflow: report the checks of the proposed commit")
    command_ = sub.add_parser("plan", help="say what `run` would do for an event file, without the network")
    command_.add_argument("event", type=Path, help="an event file, as GitHub writes it")
    command_.add_argument("--name", required=True, choices=("issues", "issue_comment"))
    command_.add_argument("--out", type=Path, required=True, help="where to write the plan (it holds the issue's text)")
    command_ = sub.add_parser("form", help="write the release list of the issue form from site/config.json")
    command_.add_argument("--check", action="store_true", help="change nothing; fail when the list differs")
    args = top.parse_args(argv)
    root = args.root.resolve()
    if args.command == "run":
        return run(env, root)
    if args.command == "status":
        return status(env, root)
    if args.command == "plan":
        planned = plan(args.name, json.loads(args.event.read_text(encoding="utf-8")), root)
        args.out.write_text(json.dumps(planned, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"intake: {planned['action']} ({planned['why']}); the plan is in {args.out}")
        return 0
    path = root / FORM_FILE
    text = path.read_text(encoding="utf-8")
    wanted = form_with_releases(text, community.load_config(root))
    if wanted == text:
        print(f"{FORM_FILE}: the release list agrees with site/config.json")
        return 0
    if args.check:
        print(f"{FORM_FILE}: the release list differs from site/config.json; run `python3 scripts/intake.py form`")
        return 1
    path.write_text(wanted, encoding="utf-8")
    print(f"{FORM_FILE}: release list written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
