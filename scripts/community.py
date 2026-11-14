"""Records of the community workspace: findings, contributions and community patches.

Standard library only. `python3 scripts/community.py --help` lists the commands.

A finding record holds dated evidence and no status. Its status (internally: its stage) is
computed, so nobody has to keep a status, a flag and the issue's labels in agreement:

    stage = the first that applies of
        closed.as      -> "withdrawn" or "not-a-defect"
        fixed_in       -> "fixed"
        answer         -> "answered"
        sent           -> "sent"
        repeated with result "reproduced" -> "confirmed"
        otherwise      -> "filed"

Interface for the site build and other tools (all take plain records, none reads the network):

    problems(root)                     every error in the records; the site build refuses on any
    load_config(root)                  provider name and the fixed list of provider releases
    load_findings(root)                every finding record, in number order; record.path is its file
    load_contributions(root)           every contribution record; record.path is its file
    load_patches(root)                 community/patches.json: the community patches, as the registry has them
    stage(record)                      the stage key, computed as above
    STATUSES, statuses(provider)       the status vocabulary in path order: key, label, description
    status_label(key, provider)        the words the site shows for a stage key
    status_description(key, provider)  one sentence, true of every finding with that status
    KINDS, OUTCOMES, DATASET_ROLES     the other fixed vocabularies, with their words
    CONTRIBUTION_CLASSES               class of a contribution and the group it belongs to
    evidence(record)                   the dated evidence of a record, oldest first
    changes(findings)                  every dated event of every finding, newest first
    last_change(record)                date of the newest evidence
    waiting_since(record)              that date while the finding is still on the path, else None
    staleness(record, today, thresholds)   how long it has waited, against the threshold of its status
    check_in_release(record, config)   releases in which to look for a correction the provider confirmed
    related(findings)                  {id: [ids]}, both directions
    patches_by_finding(patches)        {finding id: [patch, ...]}
    patches_without_finding(patches)   patches that answer no finding
    dataset_index(findings, patches)   {code: name, location, findings with their role, patches}
    release_index(findings, config)    {release id: observed in, corrected in}
    index_text(findings, config)       the one-line-per-finding table the site publishes as ledger.md
    record_path(record)                where a finding's file belongs: community/findings/0/F31.json

scripts/triage.py joins these with what only the issue tracker knows.
"""

import argparse
import datetime
import functools
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
STATES = {"proposed", "testing", "reviewing", "accepted", "rejected", "superseded"}


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Record(dict):
    """A record as a plain dict, plus the repository path of the file it was read from."""

    path = None


def load_records(root, folder, pattern):
    records = []
    for path in sorted((Path(root) / folder).rglob(pattern)):
        record = Record(read(path))
        record.path = path.relative_to(root).as_posix()
        records.append(record)
    return records


def load_config(root=ROOT):
    """Provider name and provider releases; the site and the records share this one list."""
    config = read(Path(root) / "site/config.json")
    until = config.get("older_numbering_until", LAST_LEGACY_NUMBER)
    if isinstance(until, bool) or not isinstance(until, int) or until < 0:
        raise ValueError("site/config.json: older_numbering_until is a whole number, 0 or more")
    # What differs from one dataset's repository to another's is said here and nowhere in the
    # code, so that the scripts are the same files in each. site/README.md lists these keys.
    pattern = config.get("dataset_code_pattern")
    if pattern is not None:
        if not isinstance(pattern, str):
            raise ValueError("site/config.json: dataset_code_pattern is a pattern, or it is left out")
        try:
            re.compile(pattern)
        except re.error as error:
            raise ValueError(f"site/config.json: dataset_code_pattern is not a pattern ({error})") from None
    label, form = config.get("finding_label", "finding"), config.get("finding_form", "data-finding.yml")
    if not isinstance(label, str) or not re.fullmatch(r"[a-z0-9][a-z0-9 :-]*", label):
        raise ValueError("site/config.json: finding_label is the name of a label, in small letters")
    if not isinstance(form, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.yml", form):
        raise ValueError("site/config.json: finding_form is the file name of an issue form, ending in .yml")
    notes, older = config.get("ledger_notes", []), config.get("older_numbering_note", "")
    if not isinstance(notes, list) or not all(isinstance(note, str) and not RAW_HTML.search(note) for note in notes):
        raise ValueError("site/config.json: ledger_notes is a list of sentences, without HTML")
    if not isinstance(older, str) or RAW_HTML.search(older):
        raise ValueError("site/config.json: older_numbering_note is a sentence, without HTML")
    return {
        "provider": config["provider"],
        "dataset": config.get("dataset", config["provider"]),
        "repository": config["repository"],
        "site_url": config["site_url"],
        "releases": config.get("releases", []),
        "stale_after_days": config.get("stale_after_days", {}),
        "older_numbering_until": until,
        "dataset_code_pattern": pattern,
        "lookup_example": str(config.get("lookup_example", "F1")),
        "finding_label": label,
        "finding_form": form,
        "ledger_notes": notes,
        "older_numbering_note": older,
    }


@functools.lru_cache(maxsize=None)
def default_releases():
    return frozenset(r["id"] for r in load_config()["releases"])


@functools.lru_cache(maxsize=None)
def default_older_numbering_until():
    return load_config()["older_numbering_until"]


# Finding numbers up to this one follow an older numbering; above it, the id of a finding is F
# followed by the number of its issue. The number is `older_numbering_until` in site/config.json,
# and this is its value when the file does not say: in this repository F1 to F32 follow the
# numbering of an older list, and 47 was the highest issue number when the rule began. A
# repository whose findings are numbered by their issues from the first one sets it to 0.
LAST_LEGACY_NUMBER = 47


# ----------------------------------------------------------------------------- vocabularies

# The path of a finding, in order. `key` is internal; the site shows `label`.
# {provider} is the dataset provider's name from site/config.json.
STATUSES = [
    {
        "key": "filed",
        "label": "Needs a second measurement",
        "description": "No second person is on record as having repeated this measurement on {provider}'s files.",
    },
    {
        "key": "confirmed",
        "label": "Repeated, not yet reported",
        "description": "A second person repeated the measurement and reproduced it; it has not been reported to {provider} yet.",
    },
    {
        "key": "sent",
        "label": "Reported to {provider}",
        "description": "Reported to {provider}, which has not answered yet and decides what it changes.",
    },
    {
        "key": "answered",
        "label": "Answered by {provider}",
        "description": "{provider} has answered; its answer is summarised below.",
    },
    {
        "key": "fixed",
        "label": "Resolved",
        "description": "A {provider} release covers this point; the release is named below.",
    },
    {
        "key": "not-a-defect",
        "label": "For information",
        "description": "Recorded for information: a difference in method or scope, a convention worth knowing, or a question; it is not reported as a defect.",
    },
    {
        "key": "withdrawn",
        "label": "Withdrawn",
        "description": "The observation did not hold when it was measured again; it stays listed so that nobody reports it a second time.",
    },
]
STAGE_ORDER = {s["key"]: n for n, s in enumerate(STATUSES)}
# Still on the path: something is expected to happen next.
OPEN_STAGES = ("filed", "confirmed", "sent", "answered")
# Days a finding may wait at a status before it is listed as waiting too long. site/config.json
# sets other numbers under "stale_after_days". Waiting is shown, never chased: no reminder is sent.
STALE_AFTER_DAYS = {"filed": 30, "confirmed": 30, "sent": 90, "answered": 365}
KINDS = {
    "defect": {"label": "Defect", "description": "Something in the data looks wrong: an amount, a unit, a link or a label."},
    "question": {"label": "Question", "description": "A question to {provider} about what the data means or intends."},
    "difference": {
        "label": "Difference in method or scope",
        "description": "A difference in method, scope or convention; not an error in the data.",
    },
}
OUTCOMES = {
    "confirmed": {"label": "Confirmed", "description": "{provider} confirmed the finding."},
    "declined": {"label": "Declined", "description": "{provider} declined to change its data."},
    "explained": {"label": "Explained", "description": "{provider} explained what the data means."},
}
DATASET_ROLES = {
    "subject": "The observation is in this dataset.",
    "affected": "A result of this dataset changes because it uses a dataset the finding is about.",
    "named": "Named in the finding as a supplier or for comparison.",
}
CLOSED_AS = ("withdrawn", "not-a-defect")
REPEAT_RESULTS = ("reproduced", "not-reproduced")
ROLES = {"data user", "partner", "reviewer", "maintainer", "flow curator", "importer maintainer"}
RETAINED_KINDS = {"ask", "objection", "earlier-interpretation"}
# What a contribution is. The first group can enter the patched release; the second stands
# beside the provider's numbers under its own name and never replaces them.
CONTRIBUTION_GROUPS = {
    "patched-release": "Can enter the patched release",
    "beside": "Stands beside {provider}'s numbers",
}
CONTRIBUTION_CLASSES = [
    {
        "key": "import-fix",
        "label": "Import fix",
        "group": "patched-release",
        "description": "A preparation every reader of the release needs: encoding, unit names, exchange numbers.",
    },
    {
        "key": "linking-repair",
        "label": "Linking repair",
        "group": "patched-release",
        "description": "A declared supplier that does not resolve is linked to the dataset that exists; the original declaration is kept.",
    },
    {
        "key": "re-declaration",
        "label": "Re-declaration",
        "group": "patched-release",
        "description": "A unit or label that {provider}'s own change log corrects.",
    },
    {
        "key": "variant",
        "label": "Variant",
        "group": "beside",
        "description": "A method or data variant, such as a residual electricity mix; it keeps its own name.",
    },
    {
        "key": "model",
        "label": "Model",
        "group": "beside",
        "description": "A model or a rebuilt inventory: a new inventory with its own tests.",
    },
    {
        "key": "mapping",
        "label": "Mapping",
        "group": "beside",
        "description": "A correspondence between flows, datasets or methods.",
    },
]
CONTRIBUTION_CLASS = {c["key"]: c for c in CONTRIBUTION_CLASSES}

# The fields of a finding record, in the order they are written.
FINDING_FIELDS = (
    "schema", "id", "issue", "title", "kind", "datasets", "scope", "releases", "observation",
    "exposure", "method", "reported", "repeated", "sent", "answer", "fixed_in", "closed",
    "related", "threads", "next", "retained", "notes",
)
# The dated evidence of a record, in the order of the path.
EVIDENCE = ("reported", "repeated", "sent", "answer", "fixed_in", "closed")
TEXT_FIELDS = ("observation", "exposure", "method", "notes")
# A record holds Markdown, never raw HTML: the site renders it into a page.
RAW_HTML = re.compile(r"<[A-Za-z/!]")
# A link in a record must work wherever the record is read: on the site, in the JSON, on GitHub.
RELATIVE_LINK = re.compile(r"\]\((?!https://)")
# An image loads from another host when the page opens; a heading breaks the page's outline.
MARKDOWN_IMAGE = re.compile(r"!\[")
MARKDOWN_HEADING = re.compile(r"(?m)^ {0,3}#{1,6}(\s|$)")
# A link defined apart from its text ("[1]: address") would escape the rule for links.
MARKDOWN_REFERENCE = re.compile(r"(?m)^ {0,3}\[[^\]\n]+\]:")
HTTPS_URL = re.compile(r"https://[^\s()<>\"|]+")


def statuses(provider):
    """The status vocabulary with the provider's name filled in."""
    return [{k: v.format(provider=provider) for k, v in s.items()} for s in STATUSES]


def status_label(key, provider):
    return STATUSES[STAGE_ORDER[key]]["label"].format(provider=provider)


def status_description(key, provider):
    return STATUSES[STAGE_ORDER[key]]["description"].format(provider=provider)


# ------------------------------------------------------------------------------ JSON Schema

ANNOTATIONS = {"$schema", "$id", "$defs", "$comment", "title", "description", "examples"}
JSON_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    # Stricter than JSON Schema, which also takes 2.0 for an integer.
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


@functools.lru_cache(maxsize=None)
def load_schema(name):
    """The committed JSON Schema of a record; the site publishes the same file."""
    return read(ROOT / "schema" / f"{name}.schema.json")


def json_equal(a, b):
    """Equality as JSON has it: true is not 1."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    return a == b


def schema_errors(value, schema, root=None, where=""):
    """Errors of `value` against the subset of JSON Schema that the record schemas use.

    A keyword outside the subset raises: the schema must not say more than this checks.
    """
    root = schema if root is None else root
    name = where or "the record"
    errors = []
    for keyword, rule in schema.items():
        if keyword in ANNOTATIONS:
            continue
        if keyword == "$ref":
            target = root
            for part in rule.removeprefix("#/").split("/"):
                target = target[part]
            errors += schema_errors(value, target, root, where)
        elif keyword == "type":
            allowed = [rule] if isinstance(rule, str) else rule
            if not any(JSON_TYPES[t](value) for t in allowed):
                errors.append(f"{name} must be {' or '.join(allowed)}")
        elif keyword == "const":
            if not json_equal(value, rule):
                errors.append(f"{name} must be {json.dumps(rule)}")
        elif keyword == "enum":
            if not any(json_equal(value, option) for option in rule):
                errors.append(f"{name} is {json.dumps(value)}; allowed: {', '.join(map(str, rule))}")
        elif keyword == "pattern":
            if isinstance(value, str) and not re.search(rule, value):
                errors.append(
                    f"{name} is empty" if rule == r"\S" else f"{name} does not have the required form ({rule})"
                )
        elif keyword == "not":
            if not schema_errors(value, rule, root, where):
                errors.append(
                    f"{name} holds raw HTML; write Markdown"
                    if rule == {"$ref": "#/$defs/raw_html"}
                    else f"{name} matches what the schema excludes"
                )
        elif keyword == "minimum":
            if JSON_TYPES["number"](value) and value < rule:
                errors.append(f"{name} must be at least {rule}")
        elif keyword == "uniqueItems":
            if rule and isinstance(value, list):
                seen = [json.dumps(item, sort_keys=True) for item in value]
                if len(seen) != len(set(seen)):
                    errors.append(f"{name} repeats an item")
        elif keyword == "items":
            if isinstance(value, list):
                for n, item in enumerate(value):
                    errors += schema_errors(item, rule, root, f"{where}[{n}]")
        elif keyword == "required":
            if isinstance(value, dict):
                for key in rule:
                    if key not in value:
                        errors.append(f"{where + '.' if where else ''}{key} is missing")
        elif keyword == "properties":
            if isinstance(value, dict):
                for key, sub in rule.items():
                    if key in value:
                        errors += schema_errors(value[key], sub, root, f"{where + '.' if where else ''}{key}")
        elif keyword == "additionalProperties":
            if rule is not False:
                raise ValueError("this checker supports additionalProperties: false only")
            if isinstance(value, dict):
                for key in value:
                    if key not in schema.get("properties", {}):
                        errors.append(f"{where + '.' if where else ''}{key} is not a field of the schema")
        else:
            raise ValueError(f"schema keyword {keyword!r} is not supported by this checker")
    return errors


# --------------------------------------------------------------------------------- findings


def finding_number(record):
    match = re.fullmatch(r"F([1-9][0-9]*)", str(record.get("id", "")))
    return int(match.group(1)) if match else 0


def record_path(record):
    """Where a finding's file belongs. A thousand files to a folder stays browsable."""
    number = finding_number(record if isinstance(record, dict) else {"id": record})
    return f"community/findings/{number // 1000}/F{number}.json"


def is_legacy(record, until=None):
    """Whether a finding's number follows the older numbering (`older_numbering_until` in site/config.json)."""
    until = default_older_numbering_until() if until is None else until
    return 0 < finding_number(record) <= until


def load_findings(root=ROOT):
    """Every finding record, in number order. One file per finding scales; one table does not."""
    return sorted(load_records(root, "community/findings", "F*.json"), key=finding_number)


def stage(record):
    """Where a finding stands, from its evidence. Nothing else decides it."""
    if record.get("closed"):
        return record["closed"]["as"]
    if record.get("fixed_in"):
        return "fixed"
    if record.get("answer"):
        return "answered"
    if record.get("sent"):
        return "sent"
    if (record.get("repeated") or {}).get("result") == "reproduced":
        return "confirmed"
    return "filed"


def evidence(record):
    """The dated evidence of a record, oldest first: [(date, name, block)]. Undated blocks are left out."""
    dated = [
        (record[name]["date"], n, name)
        for n, name in enumerate(EVIDENCE)
        if record.get(name) and record[name].get("date")
    ]
    return [(date, name, record[name]) for date, _, name in sorted(dated)]


def last_change(record):
    """The date of the newest evidence: when the finding last changed, not when its issue did."""
    dated = evidence(record)
    return dated[-1][0] if dated else None


def waiting_since(record):
    """Since when nothing has happened to a finding that is still on the path."""
    return last_change(record) if stage(record) in OPEN_STAGES else None


def staleness(record, today, thresholds=None):
    """How long a finding has waited at its status, computed and never stored.

    {"status", "since", "days", "threshold", "stale"}, or None once the finding is corrected
    or closed, or when its evidence carries no date. `today` is a date; `thresholds` is
    `stale_after_days` of site/config.json and overrides STALE_AFTER_DAYS per status.
    """
    since = waiting_since(record)
    if not since:
        return None
    key = stage(record)
    threshold = {**STALE_AFTER_DAYS, **(thresholds or {})}[key]
    days = (today - datetime.date.fromisoformat(since)).days
    return {"status": key, "since": since, "days": days, "threshold": threshold, "stale": days > threshold}


def check_in_release(record, config):
    """Releases in which to look for a correction: the provider confirmed the finding, no
    correction is recorded, and a release dated after the answer is registered.

    A release carries its date as `date` in site/config.json; one without a date is never listed.
    """
    answer = record.get("answer")
    if not answer or answer["outcome"] != "confirmed" or record.get("fixed_in") or record.get("closed"):
        return []
    return [r["id"] for r in config["releases"] if r.get("date") and r["date"] > answer["date"]]


def changes(findings):
    """Every dated event, newest first: [{date, id, event, stage}]. `stage` is what the event led to."""
    events = []
    for record in findings:
        for date, name, block in evidence(record):
            led_to = {
                "reported": "filed",
                "repeated": "confirmed" if block.get("result") == "reproduced" else "filed",
                "sent": "sent",
                "answer": "answered",
                "fixed_in": "fixed",
                "closed": block.get("as"),
            }[name]
            events.append({"date": date, "id": record["id"], "event": name, "stage": led_to})
    return sorted(events, key=lambda e: (e["date"], finding_number(e)), reverse=True)


def related(findings):
    """{id: [ids]} in both directions; a record needs to name the relation on one side only."""
    known = {r["id"] for r in findings}
    pairs = {r["id"]: set() for r in findings}
    for record in findings:
        for other in record.get("related", []):
            if other in known and other != record["id"]:
                pairs[record["id"]].add(other)
                pairs[other].add(record["id"])
    return {rid: sorted(others, key=lambda x: int(x[1:])) for rid, others in pairs.items()}


def retained_errors(rid, items):
    if not isinstance(items, list) or any(
        not isinstance(x, dict)
        or x.get("kind") not in RETAINED_KINDS
        or not x.get("text")
        or not x.get("evidence_url")
        for x in items
    ):
        return [f"{rid}: retained items need a kind, text and evidence"]
    return []


def markdown_errors(texts):
    """Rules for Markdown that the site renders: {where: text} -> errors."""
    errors = []
    for where, text in texts.items():
        if RELATIVE_LINK.search(text):
            errors.append(f"{where} has a link that is not a full https address")
        if MARKDOWN_IMAGE.search(text):
            errors.append(f"{where} embeds an image; link to it instead")
        if MARKDOWN_HEADING.search(text):
            errors.append(f"{where} has a heading; the page sets the headings")
        if MARKDOWN_REFERENCE.search(text):
            errors.append(f"{where} defines a link apart from its text; write [text](https://…)")
    return errors


def strings(value, where=""):
    """Every string in a record with where it is: (where, key, text)."""
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, str):
                yield f"{where + '.' if where else ''}{key}", key, item
            else:
                yield from strings(item, f"{where + '.' if where else ''}{key}")
    elif isinstance(value, list):
        for n, item in enumerate(value):
            if isinstance(item, str):
                yield f"{where}[{n}]", where.rsplit(".", 1)[-1], item
            else:
                yield from strings(item, f"{where}[{n}]")


def real_date(text):
    try:
        return datetime.date.fromisoformat(text).isoformat() == text
    except (TypeError, ValueError):
        return False


def same_person(a, b):
    return a.strip().lstrip("@").lower() == b.strip().lstrip("@").lower()


def validate_finding(record, path=None, releases=None, older_until=None):
    """Errors of one finding record: the schema first, then the rules a schema cannot express.

    `path` is the file's path in the repository when the record was read from a file.
    `releases` is the set of known release ids; by default the list in site/config.json.
    `older_until` is the last number of the older numbering; by default `older_numbering_until`
    in site/config.json.
    """
    if not isinstance(record, dict):
        return [f"{path or '?'}: a finding record is a JSON object"]
    # Errors name the file when it is known, else the finding.
    rid = path or (record.get("id") if isinstance(record.get("id"), str) else "?")
    problems = schema_errors(dict(record), load_schema("finding"))
    if problems:
        return [f"{rid}: {p}" for p in problems]
    releases = default_releases() if releases is None else releases
    errors = []
    older_until = default_older_numbering_until() if older_until is None else older_until
    legacy = is_legacy(record, older_until)
    # Identity: the path follows from the id, and above the older numbering the id follows from the issue.
    if path and path != record_path(record):
        errors.append(f"{rid}: {record['id']} belongs at {record_path(record)}")
    if not legacy and record["id"] != f"F{record['issue']}":
        errors.append(
            f"{rid}: from F{older_until + 1} on, the id is F followed by the issue number"
            f" (issue: {json.dumps(record['issue'])})"
        )
    if record["issue"] is None and not record["threads"]:
        errors.append(f"{rid}: needs an issue here or a thread elsewhere")
    # What it concerns.
    codes = [d["code"] for d in record["datasets"]]
    if len(codes) != len(set(codes)):
        errors.append(f"{rid}: datasets names a code twice")
    subjects = [d for d in record["datasets"] if d.get("role", "subject") == "subject"]
    if not subjects and not record["scope"].strip():
        errors.append(f"{rid}: name the datasets it is about, or say in scope what it concerns")
    for release in record["releases"]:
        if release not in releases:
            errors.append(f"{rid}: release {release} is not in the list of site/config.json")
    if not record["releases"] and not legacy:
        errors.append(f"{rid}: name the release it was observed in")
    # Evidence: real dates, in order, and a second person who is not the reporter.
    reported = record["reported"]
    if not legacy and not (reported["by"] and reported["date"]):
        errors.append(f"{rid}: reported needs who and when")
    if record["closed"] and not record["closed"]["date"] and not legacy:
        errors.append(f"{rid}: closed needs a date")
    for name in EVIDENCE:
        block = record[name]
        if block and block.get("date") is not None and not real_date(block["date"]):
            errors.append(f"{rid}: {name}.date is not a calendar date")
    if not errors:
        for date, name, _ in evidence(record):
            if name != "reported" and reported["date"] and date < reported["date"]:
                errors.append(f"{rid}: {name} is dated before the finding was reported")
        sent, answer = record["sent"], record["answer"]
        if sent and answer and answer["date"] < sent["date"]:
            errors.append(f"{rid}: the answer is dated before the finding was reported to the provider")
    repeated = record["repeated"]
    if repeated:
        if not reported["by"]:
            errors.append(f"{rid}: a second measurement needs a named reporter to differ from")
        elif same_person(repeated["by"], reported["by"]):
            errors.append(f"{rid}: the second measurement must come from someone other than the reporter")
    fixed = record["fixed_in"]
    if fixed and fixed["release"] not in releases:
        errors.append(f"{rid}: fixed_in.release {fixed['release']} is not in the list of site/config.json")
    # References and links.
    if record["id"] in record["related"]:
        errors.append(f"{rid}: a finding is not related to itself")
    texts = {key: record[key] for key in TEXT_FIELDS}
    for name, key in (("answer", "summary"), ("closed", "reason"), ("next", "action"), ("fixed_in", "detail")):
        if record[name] and record[name].get(key):
            texts[f"{name}.{key}"] = record[name][key]
    errors += [f"{rid}: {problem}" for problem in markdown_errors(texts)]
    return errors


def cross_record_errors(findings, patches=None):
    """Rules between records: (errors, notes). References resolve, batches agree, patches name records."""
    errors, notes = [], []
    known = {r["id"] for r in findings}
    for record in findings:
        for other in record["related"]:
            if other not in known:
                errors.append(f"{record['id']}: related names {other}, which has no record")
    batches, named = {}, {}
    for record in findings:
        if record["sent"]:
            batches.setdefault(record["sent"]["batch"], set()).add(record["sent"]["date"])
        for dataset in record["datasets"]:
            first = named.setdefault(dataset["code"], (record["id"], dataset["name"], dataset["location"]))
            if first[1:] != (dataset["name"], dataset["location"]):
                errors.append(
                    f"{record['id']}: dataset {dataset['code']} is named differently in {first[0]}"
                )
    for batch, dates in sorted(batches.items()):
        if len(dates) > 1:
            errors.append(f"batch {batch} has more than one date: {', '.join(sorted(dates))}")
    if patches:
        for patch in patches["patches"]:
            for rid in patch["findings"]:
                if rid not in known:
                    errors.append(f"patch {patch['id']} names {rid}, which has no record")
        unnamed = patches_without_finding(patches)
        if unnamed:
            notes.append(
                f"{len(unnamed)} of {len(patches['patches'])} patches name no finding: "
                + ", ".join(p["id"] for p in unnamed)
            )
    return errors, notes


# ---------------------------------------------------------------------------------- patches

PATCHES_FILE = "community/patches.json"


def load_patches(root=ROOT):
    """The community patches as scripts/patches_snapshot.py wrote them, or None when there is no file."""
    path = Path(root) / PATCHES_FILE
    return read(path) if path.exists() else None


def patch_errors(data):
    """Errors of community/patches.json. Patches are not copied into finding records."""
    if not isinstance(data, dict) or not isinstance(data.get("patches"), list):
        return [f"{PATCHES_FILE}: needs a list of patches"]
    errors = []
    source = data.get("source") if isinstance(data.get("source"), dict) else {}
    repository, ref, folder = (str(source.get(key, "")) for key in ("repository", "ref", "path"))
    plain = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*")
    if not (HTTPS_URL.fullmatch(repository) and plain.fullmatch(ref) and plain.fullmatch(folder)):
        errors.append(f"{PATCHES_FILE}: source names the repository, the ref and the folder the patches are in")
    here = f"{repository}/blob/{ref}/{folder}/"
    seen = set()
    for patch in data["patches"]:
        pid = patch.get("id", "?") if isinstance(patch, dict) else "?"
        if not isinstance(patch, dict) or not (
            re.fullmatch(r"[0-9]{4}", str(patch.get("id", "")))
            and re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", str(patch.get("slug", "")))
            and isinstance(patch.get("description"), str)
            and patch["description"].strip()
            and isinstance(patch.get("author"), str)
            and patch["author"].strip()
            and (patch.get("authorised_by") is None or isinstance(patch["authorised_by"], str))
            and isinstance(patch.get("findings"), list)
            and all(re.fullmatch(r"F[1-9][0-9]*", str(f)) for f in patch["findings"])
        ):
            errors.append(
                f"patch {pid}: needs a four-digit id, a slug, a description, an author, "
                "who authorised it (or null) and the findings it answers"
            )
            continue
        url = str(patch.get("url", ""))
        if not HTTPS_URL.fullmatch(url) or not url.startswith(here) or ".." in url:
            errors.append(f"patch {pid}: the source url leads to the patch's file in this repository")
        # The site writes these texts into pages, so the rules for record text hold here too.
        for key in ("description", "author", "authorised_by"):
            if RAW_HTML.search(patch.get(key) or ""):
                errors.append(f"patch {pid}: {key} holds raw HTML; write Markdown")
        errors += [f"patch {pid}: {e}" for e in markdown_errors({"description": patch["description"]})]
        if pid in seen:
            errors.append(f"patch {pid} is listed twice")
        seen.add(pid)
    return errors


def registry_module():
    """scripts/patches_snapshot.py, which reads the patch registry. Loaded by its path, so that
    it is found however this file was started. None where the script is not there: it belongs
    to the patch tool, and a repository without community patches has neither."""
    name = "patches_snapshot"
    if name not in sys.modules:
        if not Path(__file__).with_name(f"{name}.py").is_file():
            return None
        spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
        sys.modules[name] = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sys.modules[name])
    return sys.modules[name]


def registry_errors(root, patches):
    """The committed list of patches against the patch registry of `root`: (errors, notes).

    Patches are read from the registry, never kept by hand: the file must be exactly what
    scripts/patches_snapshot.py writes. A tree without the patch tool has nothing to compare.
    When the tool cannot be imported (the records are checked on another Python, without its
    packages), the registry is read from the source of the patch modules instead; a module
    that cannot be read that way is named in a note, and the comparison is then made by the
    check that runs inside the tool's environment.
    """
    registry = registry_module()
    if registry is None:
        return [], []
    try:
        wanted, how = registry.expected(root)
    except registry.Unreadable as problem:
        return [], [f"{PATCHES_FILE} was not compared with the patch registry: {problem}"]
    except Exception as error:  # a broken site/config.json is named by the rules for the site
        return [f"{PATCHES_FILE}: the patch registry could not be read ({type(error).__name__}: {error})"], []
    if wanted is None:
        return [], []
    again = "run `python3 scripts/patches_snapshot.py`"
    if patches is None:
        return [f"{PATCHES_FILE} is missing, and {registry.PATCH_FOLDER} holds patches: {again}"], []
    found = registry.differences(patches, wanted)
    if found:
        more = f" and {len(found) - 5} more" if len(found) > 5 else ""
        return [f"{PATCHES_FILE} differs from the patch registry (read from {how}): "
                + "; ".join(found[:5]) + more + f". Do not edit the file: {again}"], []
    return [], [f"{PATCHES_FILE} is what the patch registry gives (read from {how})"]


def patches_by_finding(patches):
    """{finding id: [patch, ...]}: the patches that answer each finding."""
    joined = {}
    for patch in (patches or {}).get("patches", []):
        for rid in patch["findings"]:
            joined.setdefault(rid, []).append(patch)
    return joined


def patches_without_finding(patches):
    return [p for p in (patches or {}).get("patches", []) if not p["findings"]]


# ---------------------------------------------------------------------------------- indexes


def dataset_index(findings, patches=None):
    """{code: {name, location, findings: [{id, role}], patches: [ids]}} for every dataset a finding lists.

    A dataset's patches are those that answer a finding the dataset is the subject of. The
    datasets a patch really changes will come from the run manifest of the patched release.
    """
    by_finding = patches_by_finding(patches)
    index = {}
    for record in findings:
        for dataset in record["datasets"]:
            role = dataset.get("role", "subject")
            entry = index.setdefault(
                dataset["code"],
                {"name": dataset["name"], "location": dataset["location"], "findings": [], "patches": []},
            )
            entry["findings"].append({"id": record["id"], "role": role})
            if role == "subject":
                for patch in by_finding.get(record["id"], []):
                    if patch["id"] not in entry["patches"]:
                        entry["patches"].append(patch["id"])
    return dict(sorted(index.items()))


def release_index(findings, config):
    """{release id: {name, findings: observed in it, corrected: corrected in it}}."""
    # `background`: what a release is built on, where a provider's release names one.
    index = {r["id"]: {"name": r["name"], "background": r.get("background"), "findings": [], "corrected": []}
             for r in config["releases"]}
    for record in findings:
        for release in record["releases"]:
            if release in index:
                index[release]["findings"].append(record["id"])
        fixed = record.get("fixed_in")
        if fixed and fixed["release"] in index:
            index[fixed["release"]]["corrected"].append(record["id"])
    return index


def link_label(url, repository=None):
    """#12 for an issue here, "another-repository #3" for one elsewhere, the host for the rest."""
    issue = re.search(r"/([^/]+)/(?:-/)?issues/(\d+)(?:#.*)?$", url)
    if not issue:
        return url.split("/")[2]
    here = url.startswith((repository or load_config()["repository"]).rstrip("/") + "/")
    return f"#{issue.group(2)}" if here else f"{issue.group(1)} #{issue.group(2)}"


def issue_url(record, repository):
    return f"{repository}/issues/{record['issue']}" if record.get("issue") else None


def discussion_links(record, repository):
    """The issue here first, then the threads elsewhere."""
    own = issue_url(record, repository)
    return ([own] if own else []) + list(record["threads"])


def concerns(record):
    """One line: the subject datasets by code, name and location, then the scope."""
    parts = [
        f"{d['code']} {d['name']} ({d['location']})"
        for d in record["datasets"]
        if d.get("role", "subject") == "subject"
    ]
    if record["scope"].strip():
        parts.append(record["scope"].strip())
    return "; ".join(parts)


def release_names(record, config):
    names = {r["id"]: r["name"] for r in config["releases"]}
    return ", ".join(names.get(release, release) for release in record["releases"]) or "—"


INDEX_HEAD = """# Findings about the {dataset} data

<!-- Generated from community/findings/ when the site is built (`python3 scripts/community.py index --out FILE`). Not kept in the repository. -->

One line per finding. The full record of a finding is its file in
[community/findings/]({repository}/tree/main/community/findings); the
[site]({site_url}findings.html) shows every record with its discussion, and
[api/v1/findings.json]({site_url}api/v1/findings.json) holds the same list for tools.

{notes}

## Status

A record holds dated evidence; its status follows from that evidence.

| Status | Meaning |
|---|---|
"""
INDEX_TABLE = """
## Findings

| # | Concerns | Observation | Release | Status | Discussion |
|---|---|---|---|---|---|
"""


def index_text(findings, config=None):
    """The one-line-per-finding table, generated from the records; the site publishes it."""
    config = config or load_config()
    provider = config["provider"]
    vocabulary = "".join(f"| **{s['label']}** | {s['description']} |\n" for s in statuses(provider))
    rows = "".join(
        f"| {r['id']} | {concerns(r)} | {r['title']} | {release_names(r, config)} | "
        f"{status_label(stage(r), provider)} | "
        + " · ".join(f"[{link_label(u, config['repository'])}]({u})" for u in discussion_links(r, config["repository"]))
        + " |\n"
        for r in findings
    )
    # What is particular to this dataset's findings is said in site/config.json (`ledger_notes`);
    # how the findings are numbered follows from `older_numbering_until`.
    until = config.get("older_numbering_until", 0)
    numbering = (f"From F{until + 1} on, the number of a finding is the number of its issue." if until
                 else "The number of a finding is the number of its issue.")
    if until and config.get("older_numbering_note"):
        numbering += " " + config["older_numbering_note"]
    notes = "\n\n".join([*config.get("ledger_notes", []), numbering])
    head = INDEX_HEAD.format(repository=config["repository"], site_url=config["site_url"],
                             dataset=config.get("dataset", provider), notes=notes)
    return head + vocabulary + INDEX_TABLE + rows


def ledger_rows(text):
    """Rows of the generated table: {id: {status, links}}. Other projects read the published copy."""
    rows, inside = {}, False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line.startswith("## Findings")
        if inside and line.startswith("| F"):
            cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
            rows[cells[0]] = {
                "status": cells[4],
                "links": set(re.findall(r"\((https://[^)]+)\)", cells[5])),
            }
    return rows


# ---------------------------------------------------------------------------- contributions


def load_contributions(root=ROOT):
    """Every contribution record, in number order."""
    return sorted(
        load_records(root, "community/contributions", "C*.json"),
        key=lambda c: int(re.sub(r"\D", "", str(c.get("id", ""))) or 0),
    )


def validate(record):
    errors = []
    required = {
        "id",
        "title",
        "status",
        "baseline",
        "layer",
        "evidence",
        "required_checks",
        "runs",
        "required_reviewers",
        "approvals",
        "objections",
        "upstream_project",
    }
    if required - record.keys():
        return ["missing fields: " + ", ".join(sorted(required - record.keys()))]
    if record["status"] not in STATES:
        errors.append("invalid status")
    for key in (
        "evidence",
        "required_checks",
        "runs",
        "required_reviewers",
        "approvals",
        "objections",
    ):
        if not isinstance(record[key], list):
            errors.append(f"{key} must be a list")
    for key, fields in [
        (
            "baseline",
            {
                "dataset",
                "release",
                "import_repository",
                "import_revision",
                "input_hashes",
            },
        ),
        (
            "layer",
            {"kind", "implementation_url", "implementation_revision", "payloads"},
        ),
    ]:
        if not isinstance(record[key], dict) or fields - record[key].keys():
            errors.append(f"{key} needs {sorted(fields)}")
    if errors:
        return errors
    if record["status"] == "accepted":
        baseline = record["baseline"]
        if not all(
            record["layer"].get(k)
            for k in ("kind", "implementation_url", "implementation_revision")
        ):
            errors.append("accepted contributions need a named, pinned implementation")
        if any(not isinstance(r, str) or not r.strip() for r in record["required_reviewers"]):
            errors.append("required reviewers must have nonempty identities")
        if not all(
            baseline.get(k)
            for k in (
                "dataset",
                "release",
                "import_repository",
                "import_revision",
                "input_hashes",
            )
        ):
            errors.append("accepted contributions need a pinned baseline and input hashes")
        if not record["required_checks"] or not record["evidence"]:
            errors.append("acceptance needs required checks and source evidence")
        # A failed or skipped required check cannot be hidden by another passed run.
        checks = {}
        for run in record["runs"]:
            if (
                not isinstance(run, dict)
                or run.get("baseline") != baseline
                or run.get("layer_revision") != record["layer"]["implementation_revision"]
            ):
                errors.append(
                    "accepted run must identify the exact baseline and candidate revision"
                )
                continue
            if not run.get("evidence_url"):
                errors.append("accepted run needs public validation evidence")
            for check in run.get("checks", []):
                checks.setdefault(check.get("id"), []).append(check)
        for name in record["required_checks"]:
            results = checks.get(name, [])
            if not results or any(
                c.get("status") != "passed" or not c.get("evidence_url") for c in results
            ):
                errors.append(f"required check {name} has missing, failed or skipped evidence")
        approved = {
            a.get("reviewer")
            for a in record["approvals"]
            if isinstance(a, dict)
            and a.get("evidence_url")
            and a.get("baseline") == baseline
            and a.get("layer_revision") == record["layer"]["implementation_revision"]
        }
        if not record["required_reviewers"] or not set(record["required_reviewers"]) <= approved:
            errors.append(
                "acceptance needs named reviewers and every approval tied to the exact baseline and layer revision"
            )
        if any(
            not isinstance(o, dict) or not o.get("disposition") or not o.get("evidence_url")
            for o in record["objections"]
        ):
            errors.append("objections need documented disposition and evidence")
    return errors


def validate_contribution_triage(record):
    """What the triage view needs from a contribution that is still in progress."""
    rid = record.get("id", "?")
    errors = retained_errors(rid, record.get("retained", []))
    if not isinstance(record.get("validation_scope", ""), str):
        errors.append(f"{rid}: validation_scope is text")
    if record.get("status") not in {"accepted", "rejected", "superseded"} and not (
        record.get("next_action") and record.get("review_role") in ROLES and record.get("evidence_url")
    ):
        errors.append(f"{rid}: open contribution needs a next action, review role and evidence")
    return errors


def contribution_text_errors(record):
    """No string of a contribution holds raw HTML, and every link is a plain https address.

    The site writes these values into pages, so the rules that hold for findings hold here.
    """
    errors = []
    for where, key, text in strings(record):
        if RAW_HTML.search(text):
            errors.append(f"{where} holds raw HTML; write Markdown")
        is_link = key.endswith("url") or where.startswith("evidence[") or key == "import_repository"
        if is_link and text and not HTTPS_URL.fullmatch(text):
            errors.append(f"{where} is not a plain https address")
    return errors


def validate_contribution(record, path=None):
    """Errors of one contribution record: the schema, then the rules for text, acceptance and triage.

    `path` is the file's path in the repository when the record was read from a file.
    """
    if not isinstance(record, dict):
        return ["a contribution record is a JSON object"]
    problems = schema_errors(dict(record), load_schema("contribution"))
    if problems:
        return problems
    errors = []
    if path and Path(path).name != f"{record['id']}.json":
        errors.append(f"{record['id']} belongs in a file named {record['id']}.json")
    return errors + contribution_text_errors(record) + validate(record) + validate_contribution_triage(record)


LAYERS_FOLDER = "community/layers"


def layer_module():
    """scripts/release_build/layer.py: what a contribution's layer file is, as the build reads it.
    One definition serves the build and this check. Reading a file needs the standard library only."""
    name = "release_build_layer"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).parent / "release_build/layer.py")
        sys.modules[name] = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sys.modules[name])
    return sys.modules[name]


def layer_errors(root, contributions):
    """Errors of the layer files in community/layers and of the records that name them.

    A contribution that changes the inventory is built as a database of its own, beside the
    patched release, from a file in community/layers. Its record names that file in
    `layer.file`. The file must be there, pass the rules of the build and name the record's
    contribution. The release build builds every file of the folder, so a file that no record
    names is an error as well.
    """
    root, errors, named = Path(root), [], {}
    for record in contributions:
        layer = record.get("layer") if isinstance(record, dict) else None
        file = layer.get("file") if isinstance(layer, dict) else None
        if not isinstance(file, str) or not file:
            continue
        rid = record.get("id", "?")
        path = Path(file)
        if path.parent.as_posix() != LAYERS_FOLDER or not path.name.startswith(f"{rid}-"):
            errors.append(f"{rid}: layer.file must be {LAYERS_FOLDER}/{rid}-<name>.json, not {file}")
            continue
        if path.name in named:
            errors.append(f"{rid}: {file} is also the layer file of {named[path.name]}")
            continue
        named[path.name] = rid
        if not (root / path).is_file():
            errors.append(f"{rid}: layer.file names {file}, which is not there")
            continue
        try:
            read_layer = layer_module().load(root / path)
        except Exception as error:  # LayerError says what is wrong; anything else is named too
            errors.append(f"{rid}: {LAYERS_FOLDER}/{error}")
            continue
        if read_layer["contribution"] != rid:
            errors.append(f"{rid}: {file} is the layer of {read_layer['contribution']}, not of {rid}")
    folder = root / LAYERS_FOLDER
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        if path.name not in named:
            errors.append(
                f"{LAYERS_FOLDER}/{path.name}: no contribution record names this file in layer.file; "
                "the release build would build it all the same"
            )
    return errors


# ------------------------------------------------------------------------------------ check


def problems(root=ROOT):
    """Everything wrong with the records under `root`: (errors, notes, what was validated).

    `check` prints this, and the site build refuses to write a page while there is an error:
    a record the check would refuse must not reach a published page either.
    """
    root = Path(root)
    errors, records = [], {}
    config = load_config(root)
    releases, older_until = {r["id"] for r in config["releases"]}, config["older_numbering_until"]
    for path in sorted((root / "community/contributions").rglob("*.json")):
        where = path.relative_to(root).as_posix()
        try:
            record = read(path)
            found = validate_contribution(record, where)
        except Exception as error:  # name the file; never stop at the first broken record
            errors.append(f"{where}: unreadable record ({type(error).__name__}: {error})")
            continue
        errors += [f"{where}: {e}" for e in found]
        if isinstance(record, dict):
            if record.get("id") in records:
                errors.append(f"{where}: duplicate contribution {record.get('id')}")
            records[record.get("id")] = record
    errors += layer_errors(root, records.values())
    for packet in read(root / "community/recommendations/tracker.json"):
        record = records.get(packet.get("contribution_id"))
        state = packet.get("status")
        if state not in {"draft", "ready", "sent", "acknowledged", "resolved"}:
            errors.append("invalid recommendation state")
        if not record:
            errors.append("recommendation references unknown contribution")
        if state != "draft" and (
            not record or record["status"] != "accepted" or not packet.get("recipient")
        ):
            errors.append(
                "ready recommendation needs accepted contribution and confirmed recipient"
            )
        if state in {"sent", "acknowledged", "resolved"} and not packet.get("delivery_url"):
            errors.append("sent recommendation needs delivery evidence")
        if state in {"acknowledged", "resolved"} and not packet.get("response_url"):
            errors.append("provider response needs evidence")
    findings, seen = [], set()
    for path in sorted((root / "community/findings").rglob("*.json")):
        where = path.relative_to(root).as_posix()
        try:
            record = read(path)
            found = validate_finding(record, where, releases, older_until)
        except Exception as error:  # name the file; never stop at the first broken record
            errors.append(f"{where}: unreadable record ({type(error).__name__}: {error})")
            continue
        errors += found
        if not isinstance(record, dict):
            continue
        if record.get("id") in seen:
            errors.append(f"{where}: duplicate finding {record.get('id')}")
        seen.add(record.get("id"))
        if not found:
            findings.append(record)
    findings.sort(key=finding_number)
    try:
        patches = load_patches(root)
        found = patch_errors(patches) if patches is not None else []
    except Exception as error:  # a broken snapshot is named, like a broken record
        patches, found = None, [f"{PATCHES_FILE}: unreadable ({type(error).__name__}: {error})"]
    errors += found
    stale, unread = ([], []) if found else registry_errors(root, patches)
    errors += stale
    patches = None if found else patches
    cross, notes = cross_record_errors(findings, patches)
    errors += cross
    notes = unread + notes
    counted = f", {len(patches['patches'])} community patches" if patches else ""
    summary = (
        f"Validated {len(findings)} findings, {len(records)} contribution records{counted} "
        "and the recommendation references."
    )
    return errors, notes, summary


def check(root):
    errors, notes, summary = problems(root)
    print("\n".join(errors) if errors else summary + "".join(f"\nNote: {note}" for note in notes))
    return int(bool(errors))


# --------------------------------------------------------------------- commands for people


def find_finding(root, rid):
    """The path of a finding's file, wherever it lies under community/findings/."""
    if not re.fullmatch(r"F[1-9][0-9]*", rid):
        raise SystemExit(f"{rid}: a finding is F followed by its number")
    matches = sorted((Path(root) / "community/findings").rglob(f"{rid}.json"))
    if len(matches) != 1:
        raise SystemExit(
            f"{rid}: {'no record' if not matches else 'more than one record'} under community/findings/"
        )
    return matches[0]


def write_record(path, record):
    """Write a record with its fields in the fixed order, as every record is written."""
    ordered = {key: record[key] for key in FINDING_FIELDS if key in record}
    ordered.update({key: value for key, value in record.items() if key not in ordered})
    Path(path).write_text(json.dumps(ordered, indent=2, ensure_ascii=False) + "\n")


def with_evidence(root, rid, name, block, replace=False, clear_next=False, next_step=None):
    """One record with one piece of evidence added: (path, record, stage before). Writes nothing.

    Evidence already recorded is kept unless `replace` is set, and the changed record must
    still be valid.
    """
    root = Path(root)
    path = find_finding(root, rid)
    record = read(path)
    if record.get(name) and not replace:
        raise SystemExit(
            f"{rid}: {name} is already recorded ({json.dumps(record[name], ensure_ascii=False)}); "
            "nothing written. Pass --replace to change it."
        )
    before = stage(record)
    record[name] = block
    if next_step is not None:
        record["next"] = next_step
    elif clear_next:
        record["next"] = None
    config = load_config(root)
    releases = {r["id"] for r in config["releases"]}
    problems = validate_finding(record, path.relative_to(root).as_posix(), releases, config["older_numbering_until"])
    if problems:
        raise SystemExit("Nothing written:\n" + "\n".join(problems))
    return path, record, before


def record_evidence(root, changed, name, kept_next=True):
    """Write the changed records, one file each and nothing else, and say what changed."""
    provider = load_config(root)["provider"]
    for path, record, before in changed:
        write_record(path, record)
        print(
            f"{record['id']}: {name} recorded in {Path(path).relative_to(Path(root)).as_posix()}; "
            f"status: {status_label(before, provider)} -> {status_label(stage(record), provider)}"
        )
        if kept_next and record.get("next"):
            print(f"{record['id']}: the next step still reads: {record['next']['action']}")


def run_command(args, root):
    """The commands that add evidence. Each writes the named record or records and nothing else."""
    next_step = {"action": args.next, "role": args.role} if args.next else None
    kept_next = next_step is None
    if args.command == "repeat":
        record = read(find_finding(root, args.finding))
        reporter = (record.get("reported") or {}).get("by")
        if not reporter:
            raise SystemExit(
                f"{args.finding}: the record names no reporter, so a second person cannot be told apart; nothing written"
            )
        if same_person(args.by, reporter):
            raise SystemExit(
                f"{args.finding}: {args.by} reported this finding; the second measurement "
                "must come from someone else. Nothing written."
            )
        block = {"by": args.by, "date": args.date, "url": args.url, "result": args.result}
        changed = [with_evidence(root, args.finding, "repeated", block, args.replace, next_step=next_step)]
        record_evidence(root, changed, "repeated", kept_next)
    elif args.command == "send":
        # Every record is checked before any is written: a batch is recorded whole or not at all.
        block = {"batch": args.batch, "date": args.date, "url": args.url}
        if len(set(args.findings)) != len(args.findings):
            raise SystemExit("A finding is named twice; nothing written.")
        changed = [
            with_evidence(root, rid, "sent", dict(block), args.replace, next_step=next_step)
            for rid in args.findings
        ]
        record_evidence(root, changed, "sent", kept_next)
    elif args.command == "answer":
        block = {"date": args.date, "outcome": args.outcome, "summary": args.summary, "url": args.url}
        changed = [with_evidence(root, args.finding, "answer", block, args.replace, next_step=next_step)]
        record_evidence(root, changed, "answer", kept_next)
    elif args.command == "fixed":
        block = {"release": args.release, "date": args.date, "url": args.url}
        if args.detail:
            block = {"release": args.release, "detail": args.detail, "date": args.date, "url": args.url}
        # The path has ended, so the old next step no longer applies.
        changed = [with_evidence(root, args.finding, "fixed_in", block, args.replace, True, next_step)]
        record_evidence(root, changed, "fixed_in", kept_next)
    elif args.command == "close":
        record = read(find_finding(root, args.finding))
        url = args.url or issue_url(record, load_config(root)["repository"]) or (record.get("threads") or [None])[0]
        block = {"as": getattr(args, "as"), "date": args.date, "reason": args.reason, "url": url}
        changed = [with_evidence(root, args.finding, "closed", block, args.replace, True, next_step)]
        record_evidence(root, changed, "closed", kept_next)
    return 0


# ---------------------------------------------------------------------------------- compare


def compare(baseline_path, candidate_path):
    baseline, candidate = read(baseline_path), read(candidate_path)
    if not baseline.get("baseline_id") or baseline.get("baseline_id") != candidate.get(
        "baseline_id"
    ):
        raise ValueError("baseline identities differ or are missing")
    scope = {
        "background",
        "method",
        "functional_unit",
        "allocation",
        "boundary",
        "geography",
    }
    if not isinstance(baseline.get("scope"), dict) or scope - baseline["scope"].keys():
        raise ValueError("comparison scope is incomplete")
    if baseline["scope"] != candidate.get("scope"):
        raise ValueError("comparison scopes differ")
    if (
        not baseline.get("metrics")
        or baseline["metrics"].keys() != candidate.get("metrics", {}).keys()
    ):
        raise ValueError("metric sets differ or are empty; omitted metrics cannot hide regressions")
    metrics = {}
    for key, before in baseline["metrics"].items():
        after = candidate["metrics"][key]
        if not before.get("unit") or before["unit"] != after.get("unit"):
            raise ValueError(f"metric {key}: incompatible units")
        values = [before.get("value"), after.get("value")]
        if any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
            for v in values
        ):
            raise ValueError(f"metric {key}: values must be finite numbers")
        delta = values[1] - values[0]
        if not math.isfinite(delta):
            raise ValueError(f"metric {key}: delta overflow")
        metrics[key] = {
            "baseline": values[0],
            "candidate": values[1],
            "delta": delta,
            "relative_delta": delta / abs(values[0]) if values[0] else None,
            "unit": before["unit"],
        }
    return {
        "baseline_id": baseline["baseline_id"],
        "scope": baseline["scope"],
        "input_sha256": {
            "baseline": digest(baseline_path),
            "candidate": digest(candidate_path),
        },
        "metrics": metrics,
        "checks": {
            "baseline": baseline.get("checks", []),
            "candidate": candidate.get("checks", []),
        },
        "interpretation": "Comparison only; scientific validation and partner review are separate.",
    }


def parser():
    top = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    # Tests and other tools point the commands at another checkout; people never need to.
    top.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    sub = top.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="validate every record and the references between them")
    command = sub.add_parser("index", help="write the one-line-per-finding table for the site")
    command.add_argument("--out", type=Path, required=True)
    command = sub.add_parser("compare", help="compare a changed build with its baseline")
    command.add_argument("baseline", type=Path)
    command.add_argument("candidate", type=Path)
    command.add_argument("--out", type=Path, required=True)

    def evidence_command(name, text, finding=True):
        command = sub.add_parser(name, help=text, description=text + " Writes that record and nothing else.")
        if finding:
            command.add_argument("finding", metavar="F<n>")
        command.add_argument("--date", required=True, help="YYYY-MM-DD")
        command.add_argument("--replace", action="store_true", help="overwrite evidence already recorded")
        command.add_argument("--next", help="the new next step, replacing the old one")
        command.add_argument("--role", default="maintainer", choices=sorted(ROLES), help="who takes the next step")
        return command

    command = evidence_command("repeat", "Record a second measurement by a second person.")
    command.add_argument("--by", required=True, help="GitHub login or name; never the reporter")
    command.add_argument("--url", required=True, help="where the second person says what they got")
    command.add_argument("--result", required=True, choices=REPEAT_RESULTS)
    command = evidence_command("send", "Record that findings were reported to the provider together.", finding=False)
    command.add_argument("findings", nargs="+", metavar="F<n>")
    command.add_argument("--batch", required=True, help="an id the findings of this batch share, such as 2026-11")
    command.add_argument("--url", required=True, help="public evidence that the batch was sent")
    command = evidence_command("answer", "Record the provider's answer, in our own words.")
    command.add_argument("--outcome", required=True, choices=sorted(OUTCOMES))
    command.add_argument("--summary", required=True, help="attributed to the provider; no person's name, no quotation")
    command.add_argument("--url", required=True, help="a public place where the answer is summarised")
    command = evidence_command("fixed", "Record that a provider release contains the correction.")
    command.add_argument("--release", required=True, help="a release id from site/config.json")
    command.add_argument("--detail", help="the file of that release that carries the correction")
    command.add_argument("--url", required=True, help="public evidence that the correction was checked")
    command = evidence_command("close", "Close a finding as withdrawn or as not a defect.")
    command.add_argument("--as", required=True, choices=CLOSED_AS)
    command.add_argument("--reason", required=True)
    command.add_argument("--url", help="where the reason is discussed; by default the finding's issue")
    return top


def main(argv=None):
    args = parser().parse_args(argv)
    root = args.root.resolve()
    if args.command == "check":
        return check(root)
    if args.command == "index":
        # The table is a build output: two pull requests that each add a finding
        # would always conflict on a committed copy.
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(index_text(load_findings(root), load_config(root)))
        print(args.out)
        return 0
    if args.command == "compare":
        # Refuse overwrite: old evidence must remain available for review.
        report = compare(args.baseline, args.candidate)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x") as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write("\n")
        print(args.out)
        return 0
    return run_command(args, root)


if __name__ == "__main__":
    sys.exit(main())
