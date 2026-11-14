"""The last run of a workflow, as GitHub and the run itself recorded it.

    python3 scripts/last_run.py --repository owner/name --out FILE
    python3 scripts/last_run.py --local --summary run.json --transcript transcript.json --out FILE

Which workflow, and what it is called on the page, is said in `site/config.json`:

    "run": {
      "name": "Build",                       what a run is called: "Build 4 of ..."
      "workflow": "build.yml",               the workflow whose last run is shown
      "artifact": "build-results",           the artifact that holds run.json and transcript.json
      "tagged": {"job": "Keep", "tags": "v"}                    optional: see below
    }

For that workflow of one repository this reads

- GitHub's own record of the last run that has ended: its number, its commit, what started
  it, how it ended, and every step with its result. Anyone can read this.
- what that run kept in its artifact: `run.json`, the run's own account of its steps
  (`scripts/runrecord/summary.py`), and `transcript.json`, every line it printed
  (`scripts/runrecord/transcript.py`). Reading an artifact needs a token (`actions: read`).

and returns one record. The site shows it as it is (`scripts/sitebuild/lastrun.py`): the last
run, not the last run that worked. A run that failed is shown as failed, with the step and
the reason; a run that kept nothing is shown with what GitHub recorded about it.

`tagged` is for a workflow that also runs for a tag and then keeps its result under that
tag: `job` is how the name of the job that keeps it begins, `tags` how such a tag begins.
What is kept under such tags is then read as well, with its files, and the page says where
this run stands as to that. The last run that was made for such a tag is read beside the
last run (`of_tag`), when it is another run: a page can then show both, the work as it
stands and the build that others should use.

`--local` makes the record of a run that did not happen on GitHub, from the two files the
run wrote: a run on a machine that holds what a public runner may not hold. GitHub has no
record of such a run, and the record says so; the page shows it marked as such.

Nothing here is trusted because it came from a run: the two files are read with limits and
checked for their shape, a key the formats do not know is refused, and the site escapes
every text of them.

    state       read | no run | not read | unreadable
    kept        read | none | expired | needs a token | unreadable     (when state is read)

Standard library only. `transport` and `fetch` are how requests leave the process; the tests
pass recorded answers, and nothing in the tests reaches the network.
"""

import argparse
import datetime
import io
import json
import os
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import github_api  # noqa: E402
from runrecord import summary, transcript  # noqa: E402

FORMAT = "sentier/last-run/2"
MAX_ARCHIVE = 30 * 1024 * 1024
MAX_FILE = 12 * 1024 * 1024
STATES = ("read", "no run", "not read", "unreadable")
KEPT = ("read", "none", "expired", "needs a token", "unreadable")
FILES = {
    "summary": ("run.json", summary.shape_errors),
    "transcript": ("transcript.json", transcript.shape_errors),
}
WORKFLOW_FILE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\.ya?ml")
PLAIN_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._-]{0,79}")


def settings(config):
    """What `site/config.json` says about the run a site shows, checked: None when it says
    nothing. Raises ValueError for a setting that can't be used."""
    value = (config or {}).get("run")
    if value is None:
        return None
    wrong = 'site/config.json: "run" is {"name", "workflow", "artifact"} and may hold "tagged"'
    if not isinstance(value, dict) or set(value) - {"name", "workflow", "artifact", "tagged"}:
        raise ValueError(wrong)
    if not all(isinstance(value.get(key), str) for key in ("name", "workflow", "artifact")):
        raise ValueError(wrong)
    if not WORKFLOW_FILE.fullmatch(value["workflow"]):
        raise ValueError(
            'site/config.json: run.workflow is the file name of a workflow, as "build.yml"'
        )
    for key in ("name", "artifact"):
        if not PLAIN_NAME.fullmatch(value[key]):
            raise ValueError(f"site/config.json: run.{key} is a short plain name")
    tagged = value.get("tagged")
    if tagged is not None and (
        not isinstance(tagged, dict)
        or set(tagged) != {"job", "tags"}
        or not all(isinstance(v, str) and PLAIN_NAME.fullmatch(v) for v in tagged.values())
    ):
        raise ValueError('site/config.json: run.tagged is {"job", "tags"}, two short plain names')
    return {**value, "tagged": tagged}


def now():
    return datetime.datetime.now(datetime.UTC).replace(microsecond=0).isoformat()


def empty(state, repository=None, run=None, note=None, read=None):
    """A record that holds no run, and says why. `read` is when GitHub was read; a record
    made without reading it has no time, so that two builds of one revision are the same."""
    return {
        "format": FORMAT,
        "state": state,
        "note": note,
        "repository": repository,
        "workflow": (run or {}).get("workflow"),
        "name": (run or {}).get("name"),
        "read": read,
    }


def fetch_address(url):
    """The bytes at an address that needs no token. At most MAX_ARCHIVE of them."""
    if not url.startswith("https://"):
        raise ValueError("an artifact is read over https")
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 - https only
        data = response.read(MAX_ARCHIVE + 1)
    if len(data) > MAX_ARCHIVE:
        raise ValueError("the artifact is larger than a run's record can be")
    return data


def text(value, limit=300):
    return value[:limit] if isinstance(value, str) else None


def run_facts(run):
    """What the page says about a run, from GitHub's record. No person is named."""
    return {
        "id": int(run["id"]),
        "number": run.get("run_number"),
        "attempt": run.get("run_attempt"),
        "url": text(run.get("html_url")),
        "event": text(run.get("event"), 40),
        "branch": text(run.get("head_branch"), 200),
        "commit": text(run.get("head_sha"), 40),
        "conclusion": text(run.get("conclusion"), 40),
        "started": text(run.get("run_started_at") or run.get("created_at"), 30),
        "ended": text(run.get("updated_at"), 30),
    }


def job_facts(job):
    return {
        "name": text(job.get("name")),
        "conclusion": text(job.get("conclusion"), 40),
        "started": text(job.get("started_at"), 30),
        "ended": text(job.get("completed_at"), 30),
        "steps": [
            {
                "number": step.get("number"),
                "name": text(step.get("name")),
                "conclusion": text(step.get("conclusion"), 40),
                "started": text(step.get("started_at"), 30),
                "ended": text(step.get("completed_at"), 30),
            }
            for step in job.get("steps") or ()
        ],
    }


def unpack(archive):
    """run.json and transcript.json of an artifact's archive, each parsed or None, and what
    was wrong. A file that is too large, unreadable or of another shape is left out."""
    found, problems = {key: None for key in FILES}, []
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            for key, (name, _) in FILES.items():
                try:
                    info = bundle.getinfo(name)
                except KeyError:
                    continue
                if info.file_size > MAX_FILE:
                    problems.append(f"{name} is larger than a run's record can be")
                    continue
                try:
                    found[key] = json.loads(bundle.read(info).decode("utf-8"))
                except ValueError:  # a text that is not UTF-8 is a ValueError too
                    problems.append(f"{name} is not JSON")
    except zipfile.BadZipFile:
        return found, ["the artifact is not an archive"]
    for key, (name, check) in FILES.items():
        if found[key] is None:
            continue
        errors = check(found[key])
        if errors:
            problems.append(f"{name}: {errors[0]}")
            found[key] = None
    return found, problems


def releases_of(github, tags):
    """What is kept under a tag that begins with `tags`, the newest first: tag, date, address
    and the files each holds. A draft is not kept yet."""
    found = []
    for release in github.get("/releases?per_page=30") or ():
        tag = release.get("tag_name") or ""
        if release.get("draft") or not tag.startswith(tags):
            continue
        found.append(
            {
                "tag": text(tag, 100),
                "published": text(release.get("published_at"), 30),
                "url": text(release.get("html_url")),
                "assets": [
                    {
                        "name": text(asset.get("name"), 200),
                        "size": asset.get("size"),
                        "url": text(asset.get("browser_download_url"), 500),
                    }
                    for asset in release.get("assets") or ()
                ],
            }
        )
    return found


def kept_by(github, run_id, artifact_name, fetch=fetch_address):
    """What a run kept: (kept, note, its own account, its transcript)."""
    listing = github.get(f"/actions/runs/{int(run_id)}/artifacts?per_page=100") or {}
    wanted = [a for a in listing.get("artifacts") or () if a.get("name") == artifact_name]
    if not wanted:
        return "none", None, None, None
    artifact = wanted[0]
    if artifact.get("expired"):
        return "expired", text(artifact.get("expires_at"), 30), None, None
    if int(artifact.get("size_in_bytes") or 0) > MAX_ARCHIVE:
        return "unreadable", "the artifact is larger than a run's record can be", None, None
    address = github.location(f"/actions/artifacts/{int(artifact['id'])}/zip")
    if address is None:
        return "needs a token", None, None, None
    found, problems = unpack(fetch(address))
    if found["summary"] is None and found["transcript"] is None:
        return "unreadable", "; ".join(problems) or "it holds no record", None, None
    return "read", "; ".join(problems) or None, found["summary"], found["transcript"]


def one_run(github, run, artifact_name, fetch=fetch_address):
    """One run as a record holds it: GitHub's record of it, and what the run kept."""
    jobs = github.get(f"/actions/runs/{int(run['id'])}/jobs?per_page=100") or {}
    kept, note, account, lines = kept_by(github, run["id"], artifact_name, fetch)
    return {
        "run": run_facts(run),
        "jobs": [job_facts(job) for job in jobs.get("jobs") or ()],
        "kept": kept,
        "kept_note": note,
        "summary": account,
        "transcript": lines,
    }


def last_for_tag(github, workflow, tags):
    """GitHub's record of the last ended run of `workflow` that was made for a tag that
    begins with `tags`, or None. GitHub names the tag where it names the branch of a run."""
    listing = github.get(f"/actions/workflows/{workflow}/runs?event=push&per_page=50") or {}
    for run in listing.get("workflow_runs") or ():
        if run.get("status") == "completed" and str(run.get("head_branch") or "").startswith(tags):
            return run
    return None


def fetch(repository, run, token=None, transport=None, fetch=fetch_address):
    """The record of the last ended run of the workflow `run` names, in `repository`."""
    github = github_api.GitHub(repository, token, transport=transport)
    try:
        listing = github.get(f"/actions/workflows/{run['workflow']}/runs?per_page=20") or {}
    except github_api.NotFound:
        return empty("no run", repository, run, "the repository has no such workflow", now())
    runs = listing.get("workflow_runs") or []
    ended = [one for one in runs if one.get("status") == "completed"]
    if not ended:
        return empty("no run", repository, run, None, now())
    last = ended[0]
    newer = runs[0] if runs[0] is not last else None
    tagged = run.get("tagged")
    of_tag = None
    if tagged:
        made = last_for_tag(github, run["workflow"], tagged["tags"])
        if made is not None and int(made["id"]) != int(last["id"]):
            of_tag = one_run(github, made, run["artifact"], fetch)
    return (
        empty("read", repository, run, read=now())
        | one_run(github, last, run["artifact"], fetch)
        | {
            "newer": None
            if newer is None
            else {
                "url": text(newer.get("html_url")),
                "status": text(newer.get("status"), 40),
            },
            "tagged": tagged,
            "releases": releases_of(github, tagged["tags"]) if tagged else [],
            "of_tag": of_tag,
        }
    )


def local(account, lines, run=None, commit=None):
    """The record of a run that did not happen on GitHub, from the two files it wrote.
    `account` is its run.json, `lines` its transcript.json; both are checked. GitHub holds no
    record of the run: the record has no `run`, and `local` says when the run was."""
    errors = summary.shape_errors(account) + transcript.shape_errors(lines)
    if errors:
        raise ValueError(errors[0])
    if commit is not None and not re.fullmatch(r"[0-9a-f]{7,40}", commit):
        raise ValueError("a commit is 7 to 40 hexadecimal digits")
    return empty("read", None, run) | {
        "run": None,
        "local": {
            "started": text(lines.get("started"), 40),
            "seconds": lines.get("seconds"),
            "commit": commit,
        },
        "newer": None,
        "jobs": [],
        "kept": "read",
        "kept_note": None,
        "summary": account,
        "transcript": lines,
        "tagged": None,
        "releases": [],
        "of_tag": None,
    }


def said(record):
    """One line for a build log: which run a site shows, and what was read of it."""
    name = record.get("name") or "run"
    name = name[:1].lower() + name[1:]
    if record["state"] != "read":
        return f"Last {name}: {record['state']}" + (
            f" ({record['note']})" if record.get("note") else ""
        )
    have = [
        what
        for key, what in (("summary", "its own account"), ("transcript", "transcript"))
        if record.get(key) is not None
    ]
    if record.get("run") is None:
        started = record["local"].get("started")
        return f"Last {name}: a run of {started} that was not on GitHub ({' and '.join(have)})"
    run = record["run"]
    line = (
        f"Last {name}: run {run['id']} of {run.get('started')}, {run.get('conclusion')}; "
        f"its record: {record['kept']}" + (f" ({' and '.join(have)})" if have else "")
    )
    of_tag = record.get("of_tag")
    if of_tag:
        made = of_tag["run"]
        line += (
            f"\nLast {name} made for a tag: run {made['id']} for {made.get('branch')}, "
            f"{made.get('conclusion')}; its record: {of_tag['kept']}"
        )
    return line


def run_errors(part):
    """What is wrong with one run of a record (GitHub's record of it, what it kept)."""
    found = []
    run = part.get("run")
    if not isinstance(run, dict) or not isinstance(run.get("id"), int):
        return ["`run` is not GitHub's record of a run"]
    if not str(run.get("url") or "").startswith("https://github.com/"):
        found.append("`run.url` is not an address on GitHub")
    if part.get("kept") not in KEPT:
        found.append("`kept` is not one of " + ", ".join(KEPT))
    if not isinstance(part.get("jobs"), list):
        found.append("`jobs` is not a list")
    for key, (name, check) in FILES.items():
        if part.get(key) is not None:
            found += [f"{name}: {error}" for error in check(part[key])]
    return found


def shape_errors(record):
    """What is wrong with a record read from a file; nothing when a page can show it."""
    if not isinstance(record, dict) or record.get("format") != FORMAT:
        return [f"not a record of format {FORMAT}"]
    if record.get("state") not in STATES:
        return ["`state` is not one of " + ", ".join(STATES)]
    if record["state"] != "read":
        return []
    if record.get("run") is None:  # a run that was not on GitHub: the run's own two files
        if not isinstance(record.get("local"), dict) or record.get("summary") is None:
            return ["a record without GitHub's record of a run holds the run's own account"]
        found = []
        for key, (name, check) in FILES.items():
            if record.get(key) is not None:
                found += [f"{name}: {error}" for error in check(record[key])]
    else:
        found = run_errors(record)
        if found and found[0].startswith("`run` is not"):
            return found
    releases = record.get("releases", [])
    if not isinstance(releases, list):
        found.append("`releases` is not a list")
    else:
        for release in releases:
            addresses = [release.get("url"), *(a.get("url") for a in release.get("assets") or ())]
            if not all(str(a or "").startswith("https://github.com/") for a in addresses):
                found.append(
                    "what is kept under a tag, or one of its files, is not at an address on GitHub"
                )
                break
    try:
        settings(
            {
                "run": {
                    "name": "x",
                    "workflow": "x.yml",
                    "artifact": "x",
                    "tagged": record.get("tagged"),
                }
            }
        )
    except ValueError:
        found.append("`tagged` is not {job, tags}")
    of_tag = record.get("of_tag")
    if of_tag is not None:
        if not isinstance(of_tag, dict):
            found.append("`of_tag` is not a run")
        else:
            found += [f"the run made for a tag: {error}" for error in run_errors(of_tag)]
    return found


def load(repository, run, snapshot=None, offline=False):
    """The record for a build of the site: from a file, else from GitHub, else one that says
    it was not read. A site is built without it rather than not built."""
    if snapshot:
        record = json.loads(Path(snapshot).read_text(encoding="utf-8"))
        errors = shape_errors(record)
        if errors:
            raise SystemExit(f"{snapshot} is not a record of a run: {errors[0]}")
        return record
    if offline:
        return empty("not read", repository, run, "this copy of the site was built without GitHub")
    name = run["name"]
    try:
        record = fetch(repository, run, os.environ.get("GITHUB_TOKEN"))
    except Exception as error:  # noqa: BLE001 - the site is built without the run
        print(f"The last {name} was not read ({type(error).__name__}); the page says so.")
        return empty(
            "unreadable", repository, run, "GitHub could not be read when the site was built"
        )
    errors = shape_errors(record)
    if errors:
        print(f"The last {name} is not shown: {github_api.plain(errors[0])}")
        return empty("unreadable", repository, run, "the record of the run could not be read")
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repository", help="owner/name")
    parser.add_argument(
        "--config", type=Path, default=Path("site/config.json"), help="Default: site/config.json"
    )
    parser.add_argument(
        "--local", action="store_true", help="A run that was not on GitHub, from its two files"
    )
    parser.add_argument("--summary", type=Path, help="With --local: the run.json of the run")
    parser.add_argument(
        "--transcript", type=Path, help="With --local: the transcript.json of the run"
    )
    parser.add_argument("--commit", help="With --local: the commit the run was made of")
    parser.add_argument("--out", type=Path, required=True, help="Where to write the record")
    args = parser.parse_args(argv)
    try:
        run = settings(json.loads(args.config.read_text(encoding="utf-8")))
        if run is None:
            raise ValueError(f'{args.config} says nothing about a run: it has no "run"')
        if args.local:
            if not (args.summary and args.transcript):
                parser.error("--local needs --summary FILE and --transcript FILE")
            read = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in (args.summary, args.transcript)
            ]
            record = local(*read, run=run, commit=args.commit)
        elif args.repository:
            record = fetch(args.repository, run, os.environ.get("GITHUB_TOKEN"))
        else:
            parser.error("give --repository owner/name, or --local with the two files of a run")
    except (OSError, ValueError) as error:
        print(f"not written: {error}")
        return 1
    errors = shape_errors(record)
    if errors:
        print(f"not written: {errors[0]}")
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(said(record))
    return 0


if __name__ == "__main__":
    sys.exit(main())
