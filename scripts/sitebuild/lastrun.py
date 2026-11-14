"""The last release build as the opening of the page "Patch and release": whether it worked,
what is blocking, what was in it, and the run itself, step by step, with every line it printed.

Everything is read from the record of scripts/last_run.py: GitHub's record of the run, and
the manifest and the transcript the run kept. Three rules hold the page to the run:

- No sentence states a result the record does not hold. A run without a record of its own
  is shown with what GitHub recorded and nothing more.
- A number is never typed. What a step does is told in site/run-steps.json, in plain words
  and without a number; every figure beside it comes from the manifest.
- The lines of the transcript are the run's own. Each is escaped for HTML and is otherwise
  unchanged; a step only groups them, in their order. A test compares the page with the
  transcript line by line.
"""

import datetime
import json
import re

from .text import day, esc, ext, plural, thousands

NOT_SHOWN = {
    "no run": "No release build has run yet.",
    "not read": "This copy of the site was built without reading GitHub, so the last run is not shown here.",
    "unreadable": "The last run could not be read from GitHub when this page was built.",
}
EVENTS = {
    "push": "after a change was accepted",
    "workflow_dispatch": "started by hand",
    "schedule": "the monthly run",
}
ENDED = {
    "success": "succeeded", "failure": "failed", "cancelled": "was cancelled",
    "timed_out": "ran out of time", "skipped": "was skipped", "startup_failure": "could not start",
}
KEPT = {
    "none": "The run kept no record of its own, so only what GitHub recorded is shown.",
    "expired": "The record the run kept is no longer on GitHub: it is kept for 90 days.",
    "needs a token": "The record the run kept was not read: this copy of the site was built without access to it.",
    "unreadable": "The record the run kept could not be read.",
}
VERDICT = {"yes": "It worked", "no": "It did not work", "unknown": "No record of its own"}
EXPORT_NAMES = {"brightway": "Brightway", "openlca": "openLCA", "ilcd": "ILCD", "simapro": "SimaPro"}
STOPPED = ("failure", "cancelled", "timed_out", "startup_failure")
SHOWN_STEPS = ("Set up job", "Complete job")  # GitHub's own two; the rest are the workflow's
RELEASE = "release"                            # the step after the run's own: what a release needs
MARKER = re.compile(r"\[(.+?)\] ")
ENDINGS = (" build", " comparison", " exports")


def moment(iso):
    try:
        return datetime.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None


def when(iso):
    """13 November 2026, 20:11 UTC"""
    at = moment(iso)
    if at is None:
        return ""
    at = at.astimezone(datetime.timezone.utc)
    return f'{day(at.date().isoformat(), long=True)}, {at:%H:%M} UTC'


def duration(seconds):
    """97 -> 1 min 37 s; 3700 -> 1 h 1 min; 0.1 -> under 1 s"""
    if 0 < seconds < 1:
        return "under 1 s"
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds} s"
    if seconds < 3600:
        return f"{seconds // 60} min {seconds % 60} s"
    return f"{seconds // 3600} h {seconds % 3600 // 60} min"


def clock(seconds):
    """The time of a line since the run began: 02:49, or 1:02:49."""
    seconds = int(seconds)
    if seconds < 3600:
        return f"{seconds // 60:02d}:{seconds % 60:02d}"
    return f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def took(run):
    start, end = moment(run.get("started")), moment(run.get("ended"))
    return duration((end - start).total_seconds()) if start and end and end >= start else None


def visible(text):
    """A line as HTML. A control character has no place in HTML: it is shown by its picture
    (U+2400 and following), so that it is neither lost nor acted on."""
    return esc("".join(chr(0x2400 + ord(c)) if ord(c) < 32 and c != "\t" else c for c in text))


def stopped_at(record):
    """The first step GitHub records as failed, cancelled or out of time: (job, step)."""
    for job in record.get("jobs") or ():
        for step in job.get("steps") or ():
            if step.get("conclusion") in STOPPED:
                return job, step
    return None, None


def sentence(text):
    """A text of the run as a sentence of the page: escaped, first letter capital, one full stop."""
    text = str(text).strip()
    return esc(text[:1].upper() + text[1:] + ("" if text.endswith((".", "!", "?")) else "."))


def number(value):
    return thousands(value) if isinstance(value, int) and not isinstance(value, bool) else None


def short(checksum, length=12):
    return f'<code title="{esc(checksum)}">{esc(str(checksum)[:length])}</code>'


# ------------------------------------------------------------------------ the three answers


def run_line(site, record):
    run = record["run"]
    build = f' {int(run["number"])}' if isinstance(run.get("number"), int) else ""
    how = EVENTS.get(run.get("event"), "")
    tag = (record.get("manifest") or {}).get("tag")
    if tag:
        how = f"for the tag <code>{esc(tag)}</code>"
    commit = f'commit <code>{esc(str(run.get("commit") or "")[:7])}</code>' if run.get("commit") else ""
    branch = f' of <code>{esc(run["branch"])}</code>' if run.get("branch") and not tag else ""
    parts = [f"Release build{build} of {when(run.get('started'))}"]
    if commit:
        parts.append(f"on {commit}{branch}")
    if how:
        parts.append(how)
    line = ", ".join(parts) + ". " + ext(run["url"], "The run on GitHub")
    newer = record.get("newer")
    if newer and str(newer.get("url") or "").startswith("https://github.com/"):
        line += f' <span class="quiet">A newer run has not ended yet: {ext(newer["url"], "see it on GitHub")}.</span>'
    return line


def worked(record):
    """(yes | no | unknown, the sentence)."""
    run, manifest = record["run"], record.get("manifest")
    conclusion, time = run.get("conclusion"), took(run)
    job, step = stopped_at(record)
    at = f' at the step “{esc(step["name"])}”' if step and step.get("name") else ""
    ended = ENDED.get(conclusion, "ended without a result")
    if manifest is None:
        if conclusion == "success":
            return "unknown", "GitHub records that the run succeeded." + (f" It took {time}." if time else "")
        return "no", f"<strong>No.</strong> GitHub records that the run {ended}{at}."
    steps = manifest["steps"]
    done = [s for s in steps if s["status"] == "completed"]
    wrong = [s for s in steps if s["status"] not in ("completed", "skipped")]
    if manifest["status"] == "completed" and conclusion == "success":
        counted = f"All {len(done)} steps completed" if len(done) == len(steps) else f"{len(done)} of {len(steps)} steps completed, and none failed"
        return "yes", f"<strong>Yes.</strong> {counted}" + (f", in {time}." if time else ".")
    if manifest["status"] == "completed":
        return "no", (f"<strong>No.</strong> The {plural(len(done), 'step')} of the build completed, "
                      f"but GitHub records that the run {ended}{at}.")
    failed = [s for s in wrong if s["status"] == "failed"]
    names = ", ".join(f"<strong>{esc(s['name'])}</strong>" for s in failed) or "none"
    return "no", (f"<strong>No.</strong> {len(done)} of {len(steps)} steps completed. "
                  f"Failed: {names}." + (f" {len(wrong) - len(failed)} did not run." if len(wrong) > len(failed) else ""))


def published(record):
    """Whether GitHub records that the job that publishes a release succeeded."""
    job = next((j for j in record.get("jobs") or () if str(j.get("name") or "").startswith("Publish")), None)
    return bool(job) and job.get("conclusion") == "success"


def blocking(site, record):
    """What stands between this run and a published release, in the run's own words."""
    run, manifest = record["run"], record.get("manifest")
    items = []
    if manifest is None:
        job, step = stopped_at(record)
        if run.get("conclusion") != "success" and step and step.get("name"):
            items.append(f"GitHub records that the step “{esc(step['name'])}” {ENDED.get(step.get('conclusion'), 'did not end well')}.")
        items.append(KEPT.get(record.get("kept"), KEPT["none"]))
        return items
    said = []
    for text in [*manifest["problems"], *manifest["not_releasable"]]:
        if text not in said:
            said.append(text)
    items += [sentence(text) for text in said]
    if not said and manifest["status"] == "completed":
        items.append("Nothing in this run keeps it from being published as a release.")
    tag = manifest.get("tag")
    if tag and published(record):
        items.append(f"It is published as the release <code>{esc(tag)}</code>: its manifest, and no file of the data.")
    elif tag:
        items.append(f"It was built for the tag <code>{esc(tag)}</code>, and that release was not published.")
    else:
        items.append("It is not a release. A release is built when a maintainer pushes a tag.")
    exports = manifest.get("exports") or {}
    if exports.get("published") is False and exports.get("note"):
        items.append(sentence(exports["note"]))
    return items


def blocking_in_short(site, record):
    """One line for the top of the page; the last step holds all of it."""
    manifest = record["manifest"]
    said = []
    for text in [*manifest["problems"], *manifest["not_releasable"]]:
        if text not in said:
            said.append(text)
    if said:
        more = f" And {plural(len(said) - 1, 'more thing')}." if len(said) > 1 else ""
        return sentence(said[0]) + more
    tag = manifest.get("tag")
    if tag and published(record):
        return f"Nothing. It is published as the release <code>{esc(tag)}</code>."
    if tag:
        return f"Nothing in the run. The release <code>{esc(tag)}</code> was not published."
    return "Nothing in the run. It is not a release: no tag was pushed for it."


def answered(site, patches, up):
    """The findings a list of patches answers, as links where the site has the finding."""
    found = sorted({f for patch in patches for f in patch["findings"]}, key=lambda f: (len(f), f))
    return ", ".join(
        f'<a href="{up}findings/{esc(f)}.html">{esc(f)}</a>' if f in site.by_id else esc(f) for f in found
    )


def release_name(site, manifest):
    release = manifest.get("provider_release") or {}
    return site.release_name(release["id"]) if release.get("id") else "A release this site does not name"


def contents(site, record, up):
    manifest = record.get("manifest")
    if manifest is None or manifest.get("provider_release") is None:
        return ["The run did not record what it read."] if manifest is not None else []
    items = []
    release = manifest["provider_release"]
    checksum = f", checksum {short(release['archive_sha256'])}" if release.get("archive_sha256") else ""
    counts = (f': {thousands(release["datasets"])} datasets and {thousands(release["exchanges"])} exchanges'
              if isinstance(release.get("datasets"), int) and isinstance(release.get("exchanges"), int) else "")
    items.append(f"{esc(release_name(site, manifest))}{counts}{checksum}.")
    return items


def contents_in_short(site, record, up):
    manifest = record["manifest"]
    if manifest.get("provider_release") is None:
        return '<span class="quiet">The run did not record what it read.</span>'
    fixes, patches = manifest["import_fixes"], manifest["patches"]
    links = answered(site, patches, up)
    return (
        f"{esc(release_name(site, manifest))}, {plural(len(fixes), 'import fix', 'import fixes')} and "
        f"{plural(len(patches), 'community patch', 'community patches')}"
        + (f", which answer {links}." if links else ".")
    )


def listed(items):
    if not items:
        return '<span class="quiet">Not recorded.</span>'
    if len(items) == 1:
        return items[0]
    return '<ul class="plain">' + "".join(f"<li>{item}</li>" for item in items) + "</ul>"


# ------------------------------------------------------------------------------- the steps


def step_texts(site):
    """What each step does, in plain words: site/run-steps.json."""
    return json.loads((site.root / "site/run-steps.json").read_text(encoding="utf-8"))["steps"]


def text_for(texts, name):
    """The words for a step: its own, else those of its kind (a contribution's), else none."""
    if name in texts:
        return texts[name]
    for ending in ENDINGS:
        if name.endswith(ending) and f"contribution{ending}" in texts:
            return texts[f"contribution{ending}"] | {"short": name}
    return texts["other"] | {"short": name, "title": name}


def steps_of(lines, names):
    """For each line of a transcript the step it belongs to, as a place in `names`: a step's
    lines begin where the run names the step, [name]. What the run prints before its first
    step belongs to the first; what it says after its last step (its own summary) to the
    place after the last, len(names). The lines keep their order: this only groups them."""
    place = {name: n for n, name in enumerate(names)}
    current, found = 0, []
    for _, text in lines:
        marked = MARKER.match(text)
        if marked and marked.group(1) in place:
            current = place[marked.group(1)]
        elif text.startswith("Release run "):
            current = len(names)
        found.append(current)
    return found


def figures(name, manifest):
    """The numbers of one step, from the manifest: [(value, what it counts)]."""
    out = []

    def add(value, label):
        if value is not None:
            out.append((value, label))

    if name == "provider build":
        release = manifest.get("provider_release") or {}
        add(number(release.get("datasets")), "datasets")
        add(number(release.get("exchanges")), "exchanges")
        audit = ((manifest.get("brightway") or {}).get("provider") or {}).get("audit")
        if audit:
            add(number(len(audit["errors"]) + len(audit["findings"])), "noted by the check")
    elif name == "patched build":
        if manifest.get("import_fixes") is not None:
            add(number(len(manifest["import_fixes"])), "import fixes")
            add(number(len(manifest["patches"])), "community patches")
        add(number((manifest.get("totals") or {}).get("datasets_changed")), "datasets changed")
    elif name == "written files":
        output = manifest.get("output") or {}
        add(number(output.get("files")), "files written")
        if isinstance(output.get("bytes"), int):
            add(f"{output['bytes'] / 1e6:,.0f} MB", "in all")
    elif name == "patch run":
        check = manifest.get("check_against_previous")
        if check:
            add(number(len(check.get("patches") or [])), "patches checked")
            add(number(len(check.get("failures") or [])), "stopped the run")
            add(number(len(check.get("warnings") or [])), "to look at")
    elif name == "comparison":
        comparison = manifest.get("comparison")
        if comparison:
            add(number(comparison["exchange_rows_compared"]), "exchanges compared")
            add(number(comparison["exchange_rows_changed"]), "differ")
            add(number(comparison["rows_no_step_explains"]), "unexplained")
    elif name == "exports":
        exports = (manifest.get("exports") or {}).get("patched")
        if exports:
            back = exports["read_back_matches"]
            add(number(len(back)), "file formats")
            add(number(sum(1 for ok in back.values() if ok)), "read back the same")
    return out


def notes(site, name, record, up):
    """What else the record says about one step, as short lines."""
    manifest, found = record["manifest"], []
    builds = manifest.get("brightway") or {}
    if name == "provider build":
        release = manifest.get("provider_release") or {}
        if release.get("archive_sha256"):
            found.append(f"{esc(release_name(site, manifest))}. Checksum of the archive: {short(release['archive_sha256'])}.")
        audit = (builds.get("provider") or {}).get("audit")
        noted = [*audit["errors"], *audit["findings"]] if audit else []
        if noted:
            more = f" And {number(len(noted) - 1)} more." if len(noted) > 1 else ""
            found.append(f'The check noted: <span class="run-said">{esc(noted[0])}</span>.{more}')
    elif name == "patched build":
        patches = manifest.get("patches") or []
        links = answered(site, patches, up)
        without = sum(1 for patch in patches if not patch["findings"])
        if links:
            found.append(f"The patches answer {links}." + (f" {plural(without, 'patch names', 'patches name')} no finding." if without else ""))
        build = builds.get("patched") or {}
        audit = build.get("audit")
        if audit:
            noted = len(audit["errors"]) + len(audit["findings"])
            found.append(f"The same check of the patched database noted {number(noted)}.")
            found.append(f"The database is named <code>{esc(build.get('database'))}</code> and marked <em>{esc(audit['marked_as'])}</em>.")
    elif name == "written files":
        output = manifest.get("output") or {}
        if output.get("fingerprint"):
            found.append(f"Fingerprint of the written files: {short(output['fingerprint'])}.")
    elif name == "patch run":
        check = manifest.get("check_against_previous")
        if check:
            earlier = check.get("compared_with")
            found.append(f"Compared with <code>{esc(earlier)}</code>." if earlier else "There is no earlier release to compare with yet.")
    elif name == "comparison":
        comparison = manifest.get("comparison")
        if comparison:
            by = comparison["rows_changed_by_step"]
            if by:
                found.append("Changed by " + ", ".join(f"<code>{esc(step)}</code> ({thousands(rows)})" for step, rows in by.items()) + ".")
            found.append(
                f"{plural(comparison['methods_compared'], 'impact method')} compared; "
                f"{number(comparison['moved_scores_no_change_explains'])} moved scores that nothing explains."
            )
    elif name == "exports":
        exports = (manifest.get("exports") or {}).get("patched")
        for file in (exports or {}).get("files", []):
            if file["kind"] in EXPORT_NAMES:
                found.append(f"<code>{esc(file['name'])}</code>, {file['bytes'] / 1e6:,.1f} MB")
    elif name == RELEASE:
        found += blocking(site, record)
    return found


def release_word(record):
    """Where the run stands as a release: (the word, how the step is drawn)."""
    if record["manifest"].get("tag"):
        return ("published", "completed") if published(record) else ("not published", "not-run")
    return ("not a release", "not-run")


def showcase(site, record, up):
    """The run as a walk through its steps. Without the script it is a page to read: the
    answers, every step with what it does and its numbers, and the whole transcript. The
    script (assets/replay.js) shows one step at a time beside the transcript and replays it."""
    manifest, run = record["manifest"], record["run"]
    texts = step_texts(site)
    steps = [dict(step) for step in manifest["steps"]]
    word, drawn = release_word(record)
    steps.append({"name": RELEASE, "status": word, "seconds": None, "reason": None, "state": drawn})
    total = len(steps)
    longest = max([s["seconds"] for s in steps if isinstance(s.get("seconds"), (int, float))] or [0]) or 1

    kind, said = worked(record)
    answers = (
        ("Did it work", f'<span class="run-{kind}">{said}</span>'),
        ("What is blocking", f'{blocking_in_short(site, record)} <a class="run-more" href="#run-step-{total}">All of it</a>'),
        ("What was in it", contents_in_short(site, record, up)),
    )
    # The stage comes first: one line says which run it is and how it ended, and the three
    # answers stand right below the stage.
    head = (
        '<div class="run-top"><h2 class="run-title" id="the-last-run">The last run</h2>'
        f'<p class="run-verdict run-{kind}">{VERDICT[kind]}</p>'
        f'<p class="run-when">{run_line(site, record)}</p></div>'
    )
    below = '<dl class="run-answers">' + "".join(f"<div><dt>{label}</dt><dd>{value}</dd></div>" for label, value in answers) + "</dl>"

    tabs, panels = "", ""
    for n, step in enumerate(steps, start=1):
        name, words = step["name"], text_for(texts, step["name"])
        state = step.get("state") or step["status"].replace(" ", "-")
        seconds = step["seconds"] if isinstance(step.get("seconds"), (int, float)) else None
        time = duration(seconds) if seconds is not None else ""
        share = f"{max(2, round(100 * seconds / longest))}%" if seconds is not None else "0"
        result = esc(step["status"]) + (f" · {time}" if time else "")
        tabs += (
            f'<li><a class="run-tab is-{esc(state)}" href="#run-step-{n}" data-step="{n - 1}">'
            f'<span class="run-tab-n">{n}</span><span class="run-tab-name">{esc(words["short"])}</span>'
            f'<span class="run-tab-time">{esc(time or step["status"])}</span>'
            f'<span class="run-tab-bar" aria-hidden="true"><span style="width:{share}"></span></span></a></li>'
        )
        shown = "".join(f"<div><dt>{esc(label)}</dt><dd>{esc(value)}</dd></div>" for value, label in figures(name, manifest))
        reason = f'<p class="run-reason">{sentence(step["reason"])}</p>' if step.get("reason") else ""
        more = "".join(f"<li>{item}</li>" for item in notes(site, name, record, up))
        panels += (
            f'<article class="run-panel" id="run-step-{n}" data-step="{n - 1}">'
            f'<p class="run-step">Step {n} of {total} · <span class="run-result is-{esc(state)}">{result}</span></p>'
            f'<h3>{esc(words["title"])}</h3><p>{esc(words["text"])}</p>{reason}'
            + (f'<dl class="run-figures">{shown}</dl>' if shown else "")
            + (f'<ul class="run-notes">{more}</ul>' if more else "")
            + "</article>"
        )

    data = record.get("transcript")
    terminal = ""
    if data is not None:
        lines = data["lines"]
        places = steps_of(lines, [step["name"] for step in manifest["steps"]])
        body = "".join(
            f'<span class="tl{" tl-step" if text.startswith("[") else ""}" data-step="{place}" '
            f'data-t="{float(t):.1f}" data-clock="{clock(t)}">{visible(text)}\n</span>'
            for (t, text), place in zip(lines, places)
        )
        build = f' {int(run["number"])}' if isinstance(run.get("number"), int) else ""
        terminal = (
            '<div class="run-term"><p class="run-term-bar"><span>What the run printed'
            f'<span class="run-term-id"> · build{build} · {esc(str(run.get("commit") or "")[:7])}</span></span>'
            '<span class="run-clock" data-run-clock></span></p>'
            f'<pre class="transcript" tabindex="0" role="region" aria-label="What the run printed">{body}</pre></div>'
        )
    controls = (
        '<p class="run-controls" hidden><button type="button" class="run-btn primary" data-run-play>Play the run</button>'
        '<button type="button" class="run-btn" data-run-prev>Back</button>'
        '<button type="button" class="run-btn" data-run-next>Next</button></p>'
    )
    stage = (
        f'<div class="run-stage"><ol class="run-tabs" aria-label="The steps of the run">{tabs}</ol>{controls}'
        f'<div class="run-body"><div class="run-side"><div class="run-panels">{panels}</div></div>{terminal}</div></div>'
    )
    note = ""
    if data is not None:
        ended = "It ended with status 0." if data["exit_code"] == 0 else f"It ended with status {int(data['exit_code'])}."
        if data.get("stopped_by"):
            ended = f"It was stopped ({esc(data['stopped_by'])})."
        cut = " The run printed more than is kept here." if data.get("cut") else ""
        note = (
            f'<p class="note run-note">{plural(len(data["lines"]), "line")}, exactly as the run printed them, each with its time since the start. '
            f"{ended}{cut} The replay shortens the waits and changes nothing else. "
            f'SHA-256 of the lines: <code>{esc(data["sha256"])}</code>. '
            f'The same record as a file: <a href="{up}api/v1/last-run.json"><code>api/v1/last-run.json</code></a>.</p>'
        )
    return (
        f'<section class="run" data-run aria-labelledby="the-last-run">{head}{stage}{below}{note}</section>'
        f'<script src="{up}assets/replay.js" defer></script>'
    )


# ------------------------------------------------ a run without a record of its own (plain)


def steps_table(record):
    """The steps GitHub recorded, for a run that kept no manifest."""
    rows = []
    for job in record.get("jobs") or ():
        for step in job.get("steps") or ():
            name = str(step.get("name") or "")
            if name in SHOWN_STEPS or name.startswith("Post "):
                continue
            start, end = moment(step.get("started")), moment(step.get("ended"))
            time = duration((end - start).total_seconds()) if start and end and end >= start else ""
            rows.append((name, step.get("conclusion") or "not run", time))
    if not rows:
        return ""
    head = ("Step", "Result", "Time")
    lines = ""
    for name, result, time in rows:
        mark = "" if result in ("success", "skipped") else ' class="run-failed"'
        lines += f'<tr role="row"{mark}>' + "".join(
            f'<td role="cell" data-label="{label}">{esc(cell)}</td>' for label, cell in zip(head, (name, result, time))
        ) + "</tr>"
    return (
        '<div class="table-wrap"><table role="table" class="cols-3 key-short"><thead role="rowgroup"><tr role="row">'
        + "".join(f'<th role="columnheader" scope="col">{label}</th>' for label in head)
        + f'</tr></thead><tbody role="rowgroup">{lines}</tbody></table></div>'
    )


def plain(site, record, up):
    """A run that kept no manifest: what GitHub recorded, and the transcript if there is one."""
    kind, said = worked(record)
    facts = (
        ("Run", run_line(site, record)),
        ("Did it work", f'<span class="run-{kind}">{said}</span>'),
        ("What is blocking", listed(blocking(site, record))),
        ("What was in it", listed(contents(site, record, up))),
    )
    panel = '<dl class="panel run-facts">' + "".join(f"<div><dt>{label}</dt><dd>{value}</dd></div>" for label, value in facts) + "</dl>"
    table = steps_table(record)
    data, printed = record.get("transcript"), ""
    if data is not None:
        body = "".join(
            f'<span class="tl{" tl-step" if text.startswith("[") else ""}" data-step="0" data-t="{float(t):.1f}" '
            f'data-clock="{clock(t)}">{visible(text)}\n</span>' for t, text in data["lines"]
        )
        printed = (
            '<h3 id="what-the-run-printed">What the run printed</h3>'
            f'<p>{plural(len(data["lines"]), "line")}, exactly as the run printed them. SHA-256 of the lines: <code>{esc(data["sha256"])}</code>.</p>'
            f'<div class="run-term"><pre class="transcript" tabindex="0" role="region" aria-label="What the run printed">{body}</pre></div>'
        )
    return (
        '<section class="run run-plain" aria-labelledby="the-last-run"><h2 class="run-title" id="the-last-run">The last run</h2>'
        + panel + (f'<h3 id="steps-of-the-run">Step by step</h3>{table}' if table else "") + printed + "</section>"
    )


def last_run(site, up=""):
    """The block a prose page asks for with <!-- generated: last-run -->."""
    record = site.last_run
    if record["state"] != "read":
        return (
            '<section class="run run-plain" aria-labelledby="the-last-run"><h2 class="run-title" id="the-last-run">The last run</h2>'
            f'<p class="list-none">{esc(NOT_SHOWN[record["state"]])}</p></section>'
        )
    if record.get("manifest") is None:
        return plain(site, record, up)
    return showcase(site, record, up)


# ---------------------------------------------------------------- releases and their packages


def megabytes(size):
    return f"{size / 1e6:,.1f} MB" if isinstance(size, (int, float)) and not isinstance(size, bool) else ""


def package_rows(record):
    """The files of the last run that a release is made of, each with where it can be had:
    [{kind, label, name, size, sha256, same, url}]. `url` is a file of the newest release
    with the same name, or None: a file that no release holds can't be downloaded."""
    manifest = record.get("manifest") or {}
    exports = (manifest.get("exports") or {}).get("patched")
    if not exports:
        return []
    newest = (record.get("releases") or [{}])[0]
    held = {asset.get("name"): asset.get("url") for asset in newest.get("assets") or ()}
    rows = []
    for file in exports["files"]:
        if file["kind"] not in EXPORT_NAMES:
            continue
        rows.append({
            "kind": file["kind"], "label": EXPORT_NAMES[file["kind"]], "name": file["name"],
            "size": megabytes(file["bytes"]), "sha256": file["sha256"],
            "same": exports["read_back_matches"].get(file["kind"]), "url": held.get(file["name"]),
        })
    return rows


def packages(site, up=""):
    """The block <!-- generated: release-packages -->: the published releases with the files
    each holds, and the files of the last run with their size, their checksum and whether
    they can be downloaded. Nothing is offered that no release holds."""
    record = site.last_run
    if record["state"] != "read":
        return ('<div class="packages" id="release-packages" data-packages><p class="list-none">'
                "The releases were not read from GitHub for this copy of the site.</p></div>")
    releases = record.get("releases") or []
    if releases:
        listed_ = '<ul class="plain releases">' + "".join(
            f'<li><strong><code>{esc(release["tag"])}</code></strong> <span class="quiet">· {day(release["published"], long=True)}</span> · '
            f'{ext(release["url"], "the release on GitHub")}'
            + "".join(f'<br>{ext(asset["url"], "<code>" + esc(asset["name"]) + "</code>")} <span class="quiet">{megabytes(asset["size"])}</span>'
                      for asset in release["assets"])
            + "</li>"
            for release in releases
        ) + "</ul>"
    else:
        listed_ = '<p class="list-none">No release has been published yet.</p>'
    rows = package_rows(record)
    table = ""
    if rows:
        run = record["run"]
        head = ("File", "For", "Size", "SHA-256", "Where")
        lines = ""
        for row in rows:
            where = ext(row["url"], "Download") if row["url"] else "not published"
            read = "" if row["same"] else ' <span class="run-no"><strong>did not read back the same</strong></span>'
            cells = (f'<code>{esc(row["name"])}</code>{read}', esc(row["label"]), esc(row["size"]), short(row["sha256"]), where)
            lines += '<tr role="row">' + "".join(
                f'<td role="cell" data-label="{label}">{cell}</td>' for label, cell in zip(head, cells)
            ) + "</tr>"
        build = f' {int(run["number"])}' if isinstance(run.get("number"), int) else ""
        table = (
            f'<p>The files of the last run (build{build}, {when(run.get("started"))}), each read back after it was written:</p>'
            '<div class="table-wrap"><table role="table" class="cols-5 key-short"><thead role="rowgroup"><tr role="row">'
            + "".join(f'<th role="columnheader" scope="col">{label}</th>' for label in head)
            + f'</tr></thead><tbody role="rowgroup">{lines}</tbody></table></div>'
        )
    return f'<div class="packages" id="release-packages" data-packages>{listed_}{table}</div>'


def rail_box(site, up=""):
    """The same files, small, beside the text under "On this page". The script shows the
    box once the reader has scrolled past the releases; without the script it is always there."""
    record = site.last_run
    rows = package_rows(record) if record["state"] == "read" else []
    if not rows:
        return ""
    newest = (record.get("releases") or [{}])[0]
    title = f'Release <code>{esc(newest["tag"])}</code>' if newest.get("tag") else "Release packages"
    items = "".join(
        f'<li><span class="downloads-name">{esc(row["label"])}</span><span class="quiet">{esc(row["size"])}</span>'
        + (ext(row["url"], "Download") if row["url"] else '<span class="quiet">not published</span>')
        + "</li>"
        for row in rows
    )
    return (
        '<div class="downloads" data-show-after="release-packages">'
        f'<p class="card-label">{title}</p><ul>{items}</ul>'
        '<a class="arrow" href="#releases">About the releases</a></div>'
    )


def public_record(record):
    """The record as a file of the site: as it was read, without the lists of dataset
    numbers of each patch (the manifest of a release holds them)."""
    if record.get("manifest") is None:
        return record
    manifest = dict(record["manifest"])
    manifest["patches"] = [{k: v for k, v in patch.items() if k != "datasets"} for patch in manifest.get("patches") or ()]
    return record | {"manifest": manifest}
