"""The last run of a workflow as the opening of a page: whether it worked, what is blocking,
what was in it, and the run itself, step by step, with every line it printed.

Everything is read from the record of scripts/last_run.py: GitHub's record of the run, and
the two files the run kept, its own account (run.json) and its transcript. Which workflow
that is, and what its runs are called, is said in site/config.json under "run". Three rules
hold the page to the run:

- No sentence states a result the record does not hold. A run without an account of its own
  is shown with what GitHub recorded and nothing more.
- A number is never typed. What a step does is told in site/run-steps.json, in plain words
  and without a number; every figure beside it, and every note, is the run's own account.
- The lines of the transcript are the run's own. Each is escaped for HTML and is otherwise
  unchanged; a step only groups them, in their order. A test compares the page with the
  transcript line by line.

Nothing here knows a dataset or a tool: a step is what the run names, with the words the
site's own file has for it. The page adds no step of its own. A step the run says it could not run
in this place ("not run here") is drawn as open, with the run's reason, and is no failure. A run that did not happen
on GitHub is shown marked as such.
"""

import datetime
import json
import re

from .text import day, esc, ext, plural, thousands

NOT_SHOWN = {
    "not read": "This copy of the site was built without reading GitHub, so the last run is not shown here.",
    "unreadable": "The last run could not be read from GitHub when this page was built.",
}
EVENTS = {
    "push": "after a change was accepted",
    "workflow_dispatch": "started by hand",
    "schedule": "started by its schedule",
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
STOPPED = ("failure", "cancelled", "timed_out", "startup_failure")
SHOWN_STEPS = ("Set up job", "Complete job")  # GitHub's own two; the rest are the workflow's
# A run that was made for a tag is kept under that tag. Every sentence about that stands here,
# in one place. The words are plain: a build, its tag, its files. None of them claims what
# only a provider can do with its own data. The page adds no step for this: the steps on the
# page are the run's own, and where a run stands as to its tag is said with the answers.
TAG = {
    "nothing blocks": "Nothing in this run.",
    "is kept": "It is kept under the tag <code>{tag}</code>: its manifest, and no file of the data.",
    "was not kept": "It was made for the tag <code>{tag}</code>, and it was not kept.",
    "no tag": "It has no tag. A maintainer gives a tag to the build that others should use.",
    "none yet": "No build has a tag yet.",
    "not read": "The tagged builds were not read from GitHub for this copy of the site.",
    "on GitHub": "the tag on GitHub",
    "box": "Files of the last build", "box of": "Build <code>{tag}</code>", "about": "About tagged builds",
    "where not": "not offered",
}
NO_FAILURE = ("completed", "skipped", "not run here")
DRAWN = {"not run here": "open"}               # a step this place can't run is open, not left undone
FINDING = re.compile(r"\b[A-Z]{1,4}[0-9]{1,6}\b")
SHA256 = re.compile(r"[0-9a-f]{64}")
TAG_IDS = "tag-"                               # what the ids of the second run on a page begin with
MARKER = re.compile(r"\[(.+?)\] ")


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


TOKENS = re.compile(
    r"\b(completed|passed|applied|matches)\b|\b(failed|differs|not run|refused)\b|\b([0-9a-f]{12,64})\b"
)


def marked(text):
    """A line of the transcript with its parts told apart for the eye: the step it names, a
    command, a word that says how something ended, a checksum. Nothing is added to the text and
    nothing is taken from it: the parts are wrapped, each escaped as the rest of the line is.
    The run prints no colour of its own; these are the page's marks, by the words alone."""
    def words(part):
        out, at = "", 0
        for found in TOKENS.finditer(part):
            kind = "ok" if found.group(1) else "bad" if found.group(2) else "sum"
            out += visible(part[at:found.start()]) + f'<i class="tk-{kind}">{visible(found.group(0))}</i>'
            at = found.end()
        return out + visible(part[at:])

    if text.startswith("[") and "]" in text:
        end = text.index("]") + 1
        return f'<b class="tk-step">{visible(text[:end])}</b>{words(text[end:])}'
    plain = text.lstrip(" ")
    if plain.startswith("$ "):
        return f'{visible(text[: len(text) - len(plain)])}<i class="tk-prompt">$</i>{visible(plain[1:])}'
    return words(text)


def line_class(text):
    return "tl" + (" tl-step" if text.startswith("[") else " tl-cmd" if text.lstrip(" ").startswith("$ ") else "")


def line(number, t, text, place=0, ids=""):
    """One line of the transcript. Its time is drawn by the stylesheet and is no text of the
    page, so that what a reader copies is what the run printed. The time is also the link to
    the line, as a line number is in a log on GitHub: a line can be pointed at."""
    at = clock(t)
    return (
        f'<span class="{line_class(text)}" id="{ids}run-line-{number}" data-step="{place}" data-t="{float(t):.1f}" '
        f'data-clock="{at}"><a class="tl-at" href="#{ids}run-line-{number}" tabindex="-1" aria-hidden="true" '
        f'data-clock="{at}"></a>{marked(text)}\n</span>'
    )


def stopped_at(record):
    """The first step GitHub records as failed, cancelled or out of time: (job, step)."""
    for job in record.get("jobs") or ():
        for step in job.get("steps") or ():
            if step.get("conclusion") in STOPPED:
                return job, step
    return None, None


# The marks on the terminal's buttons. Each is drawn with the colour of its button's text.
def icon(shape, filled=False):
    paint = 'fill="currentColor" stroke="none"' if filled else (
        'fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"')
    return f'<svg class="run-icon" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" focusable="false" {paint}>{shape}</svg>'


ICONS = {
    "play": icon('<path d="M4.5 2.8v10.4a.6.6 0 0 0 .9.5l8.4-5.2a.6.6 0 0 0 0-1L5.4 2.3a.6.6 0 0 0-.9.5z"/>', filled=True),
    "end": icon('<path d="M3 2.8v10.4a.6.6 0 0 0 .9.5L10.5 9.6v3.6c0 .4.3.8.8.8h.9c.4 0 .8-.4.8-.8V2.8c0-.4-.4-.8-.8-.8h-.9c-.5 0-.8.4-.8.8v3.6L3.9 2.3a.6.6 0 0 0-.9.5z"/>', filled=True),
    "wrap": icon('<path d="M2 4h12M2 8h9.2a2.3 2.3 0 0 1 0 4.6H8.4m0 0 1.7-1.7m-1.7 1.7 1.7 1.7M2 12h3.2"/>'),
    "copy": icon('<rect x="5.5" y="5.5" width="8" height="8" rx="1.6"/><path d="M10.5 5.5v-1.4A1.6 1.6 0 0 0 8.9 2.5H4.1a1.6 1.6 0 0 0-1.6 1.6v4.8a1.6 1.6 0 0 0 1.6 1.6h1.4"/>'),
    "full": icon('<path d="M2.5 6V2.5H6M10 2.5h3.5V6M13.5 10v3.5H10M6 13.5H2.5V10"/>'),
    "small": icon('<path d="M6 2.5V6H2.5M13.5 6H10V2.5M10 13.5V10h3.5M2.5 10H6v3.5"/>'),
}


# ---------------------------------------------------------------------- a text of the run


def short(checksum, length=12):
    return f'<code title="{esc(checksum)}">{esc(str(checksum)[:length])}</code>'


def inline(site, text, up=""):
    """A text of the run as HTML. It is plain and is escaped; two things in it are read:
    `a name` between backquotes is shown as code (a whole SHA-256 shortened, with all of it in
    the title), and the number of a finding this site holds becomes a link to the finding."""
    def words(part):
        out, at = "", 0
        for found in FINDING.finditer(part):
            if found.group(0) not in site.by_id:
                continue
            out += esc(part[at:found.start()]) + f'<a href="{up}findings/{esc(found.group(0))}.html">{esc(found.group(0))}</a>'
            at = found.end()
        return out + esc(part[at:])

    parts = str(text).split("`")
    if len(parts) % 2 == 0:  # a backquote without its partner is a character like any other
        return words(str(text))
    return "".join(
        words(part) if n % 2 == 0 else (short(part) if SHA256.fullmatch(part) else f"<code>{esc(part)}</code>")
        for n, part in enumerate(parts)
    )


def sentence(site, text, up=""):
    """A text of the run as a sentence of the page: first letter capital, one full stop."""
    text = str(text).strip()
    return inline(site, text[:1].upper() + text[1:] + ("" if text.endswith((".", "!", "?", ".”")) else "."), up)


def named(record):
    """What a run of the workflow is called on the page: "Build"."""
    return str(record.get("name") or "Run")


def number_of(run):
    return f' {int(run["number"])}' if run and isinstance(run.get("number"), int) else ""


# ------------------------------------------------------------------------ the three answers


def run_line(site, record):
    run, account = record.get("run"), record.get("summary") or {}
    tag = account.get("tag")
    if run is None:  # a run that was not on GitHub
        local = record["local"]
        commit = f', on commit <code>{esc(str(local["commit"])[:7])}</code>' if local.get("commit") else ""
        return (
            f"{esc(named(record))} of {when(local.get('started'))}{commit}. "
            '<strong class="run-elsewhere">Not a run on GitHub.</strong> It ran on a machine of its own, GitHub holds no '
            "record of it, and what is shown here is what the run wrote about itself."
        )
    how = EVENTS.get(run.get("event"), "")
    if tag:
        how = f"for the tag <code>{esc(tag)}</code>"
    commit = f'commit <code>{esc(str(run.get("commit") or "")[:7])}</code>' if run.get("commit") else ""
    branch = f' of <code>{esc(run["branch"])}</code>' if run.get("branch") and not tag else ""
    parts = [f"{esc(named(record))}{number_of(run)} of {when(run.get('started'))}"]
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
    """(yes | no | unknown, the sentence). On GitHub a run worked when the run says so and
    GitHub says so. A step that can't run in this place is no failure."""
    run, account = record.get("run"), record.get("summary")
    if run is None:
        conclusion, seconds = "success", record["local"].get("seconds")
        time = duration(seconds) if isinstance(seconds, (int, float)) and not isinstance(seconds, bool) else None
    else:
        conclusion, time = run.get("conclusion"), took(run)
    job, step = stopped_at(record)
    at = f' at the step “{esc(step["name"])}”' if step and step.get("name") else ""
    ended = ENDED.get(conclusion, "ended without a result")
    if account is None:
        if conclusion == "success":
            return "unknown", "GitHub records that the run succeeded." + (f" It took {time}." if time else "")
        return "no", f"<strong>No.</strong> GitHub records that the run {ended}{at}."
    steps = account["steps"]
    done = [s for s in steps if s["status"] == "completed"]
    here = [s for s in steps if s["status"] == "not run here"]
    wrong = [s for s in steps if s["status"] not in NO_FAILURE]
    if account["status"] == "completed" and conclusion == "success":
        counted = f"All {len(done)} steps completed" if len(done) == len(steps) else f"{len(done)} of {len(steps)} steps completed, and none failed"
        elsewhere = f" {plural(len(here), 'step was', 'steps were')} not run here." if here else ""
        return "yes", f"<strong>Yes.</strong> {counted}" + (f", in {time}." if time else ".") + elsewhere
    if account["status"] == "completed":
        return "no", (f"<strong>No.</strong> The {plural(len(done), 'step')} of the run completed, "
                      f"but GitHub records that the run {ended}{at}.")
    failed = [s for s in wrong if s["status"] == "failed"]
    names = ", ".join(f"<strong>{esc(s['name'])}</strong>" for s in failed) or "none"
    return "no", (f"<strong>No.</strong> {len(done)} of {len(steps)} steps completed. "
                  f"Failed: {names}." + (f" {len(wrong) - len(failed)} did not run." if len(wrong) > len(failed) else ""))


def kept_under_tag(record):
    """Whether GitHub records that the job that keeps a run under its tag succeeded."""
    tagged = record.get("tagged")
    if not tagged:
        return False
    job = next((j for j in record.get("jobs") or () if str(j.get("name") or "").startswith(tagged["job"])), None)
    return bool(job) and job.get("conclusion") == "success"


def for_tag(record):
    """The tag a run was made for, on a site whose workflow keeps such runs; else None."""
    return (record.get("summary") or {}).get("tag") if record.get("tagged") else None


def blocking(site, record, up=""):
    """What stands between this run and the use of its result, in the run's own words; and,
    for a workflow that keeps the runs made for a tag, where this run stands as to that."""
    run, account = record.get("run"), record.get("summary")
    items = []
    if account is None:
        job, step = stopped_at(record)
        if run.get("conclusion") != "success" and step and step.get("name"):
            items.append(f"GitHub records that the step “{esc(step['name'])}” {ENDED.get(step.get('conclusion'), 'did not end well')}.")
        items.append(KEPT.get(record.get("kept"), KEPT["none"]))
        return items
    items += [sentence(site, text, up) for text in account["blocking"]]
    if not items and account["status"] == "completed":
        items.append(TAG["nothing blocks"])
    tag = for_tag(record)
    if tag and kept_under_tag(record):
        items.append(TAG["is kept"].format(tag=esc(tag)))
    elif tag:
        items.append(TAG["was not kept"].format(tag=esc(tag)))
    elif record.get("tagged"):
        items.append(TAG["no tag"])
    items += [sentence(site, text, up) for text in account["remarks"]]
    return items


def contents(site, record, up=""):
    account = record.get("summary")
    return [inline(site, text, up) for text in account["contents"]] if account else []


def listed(items):
    if not items:
        return '<span class="quiet">Not recorded.</span>'
    if len(items) == 1:
        return items[0]
    return '<ul class="plain">' + "".join(f"<li>{item}</li>" for item in items) + "</ul>"


# ------------------------------------------------------------------------------- the steps


def step_texts(site):
    """What each step does, in plain words: site/run-steps.json, a file of the site's own.
    (the words of the steps, and which step stands for the steps whose names end alike)."""
    path = site.root / "site/run-steps.json"
    if not path.is_file():
        return {}, {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("steps") or {}, data.get("endings") or {}


def text_for(texts, endings, name):
    """The words for a step: its own, else those of the steps whose names end as its name
    does, else none but its name."""
    if name in texts:
        return texts[name]
    for ending, kind in endings.items():
        if name.endswith(ending) and kind in texts:
            return texts[kind] | {"short": name}
    return (texts.get("other") or {"text": ""}) | {"short": name, "title": name}


def steps_of(lines, names, closing=None):
    """For each line of a transcript the step it belongs to, as a place in `names`: a step's
    lines begin where the run names the step, [name]. What the run prints before its first
    step belongs to the first; what it says after its last step (lines that begin with
    `closing`, and what follows them) to the place after the last, len(names). The lines
    keep their order: this only groups them."""
    place = {name: n for n, name in enumerate(names)}
    current, found = 0, []
    for _, text in lines:
        marked = MARKER.match(text)
        if marked and marked.group(1) in place:
            current = place[marked.group(1)]
        elif closing and text.startswith(closing):
            current = len(names)
        found.append(current)
    return found


def figure(value):
    """A figure as the run states it: a count with its thousands apart, a text as it is."""
    return thousands(value) if isinstance(value, int) and not isinstance(value, bool) else str(value)


def showcase(site, record, up, title="The last run", ids=""):
    """The run as a walk through its steps. Without the script it is a page to read: the
    answers, every step with what it does and its numbers, and the whole transcript. The
    script (assets/replay.js) shows one step at a time beside the transcript and replays it."""
    account, run = record["summary"], record.get("run")
    texts, endings = step_texts(site)
    steps = [dict(step) for step in account["steps"]]
    # The steps are the run's own and the page adds none: a step the run did not have would
    # look as if something had been left undone.
    total = len(steps)
    longest = max([s["seconds"] for s in steps if isinstance(s.get("seconds"), (int, float))] or [0]) or 1

    kind, said = worked(record)
    blocks = listed(blocking(site, record, up))
    answers = (
        ("Did it work", f'<span class="run-{kind}">{said}</span>'),
        ("What is blocking", blocks),
        ("What was in it", listed(contents(site, record, up))),
    )
    # The stage comes first: one line says which run it is and how it ended, and the three
    # answers stand right below the stage.
    head = (
        f'<div class="run-top"><h2 class="run-title" id="{ids}the-last-run">{esc(title)}</h2>'
        f'<p class="run-verdict run-{kind}">{VERDICT[kind]}</p>'
        f'<p class="run-when">{run_line(site, record)}</p></div>'
    )
    below = '<dl class="run-answers">' + "".join(f"<div><dt>{label}</dt><dd>{value}</dd></div>" for label, value in answers) + "</dl>"

    tabs, panels = "", ""
    for n, step in enumerate(steps, start=1):
        name, words = step["name"], text_for(texts, endings, step["name"])
        state = DRAWN.get(step["status"], step["status"].replace(" ", "-"))
        seconds = step["seconds"] if isinstance(step.get("seconds"), (int, float)) else None
        time = duration(seconds) if seconds is not None else ""
        # The bar is the step's share of the longest step's time; a step without a time has none.
        bar = (f'<span class="run-tab-bar" aria-hidden="true"><span style="width:{max(2, round(100 * seconds / longest))}%">'
               "</span></span>") if seconds is not None else ""
        result = esc(step["status"]) + (f" · {time}" if time else "")
        tabs += (
            f'<li><a class="run-tab is-{esc(state)}" href="#{ids}run-step-{n}" data-step="{n - 1}">'
            f'<span class="run-tab-n">{n}</span><span class="run-tab-name">{esc(words["short"])}</span>'
            f'<span class="run-tab-time">{esc(time or step["status"])}</span>{bar}</a></li>'
        )
        shown = "".join(
            f'<div><dt>{esc(one["label"])}</dt><dd>{esc(figure(one["value"]))}</dd></div>' for one in step.get("figures") or ()
        )
        reason = f'<p class="run-reason">{sentence(site, step["reason"], up)}</p>' if step.get("reason") else ""
        more = "".join(f"<li>{inline(site, note, up)}</li>" for note in step.get("notes") or ())
        about = f'<p>{esc(words["text"])}</p>' if words.get("text") else ""
        panels += (
            f'<article class="run-panel" id="{ids}run-step-{n}" data-step="{n - 1}">'
            f'<p class="run-step">Step {n} of {total} · <span class="run-result is-{esc(state)}">{result}</span></p>'
            f'<h3>{esc(words["title"])}</h3>{about}{reason}'
            + (f'<dl class="run-figures">{shown}</dl>' if shown else "")
            + (f'<ul class="run-notes">{more}</ul>' if more else "")
            + "</article>"
        )

    data = record.get("transcript")
    terminal = ""
    if data is not None:
        lines = data["lines"]
        places = steps_of(lines, [step["name"] for step in account["steps"]], account.get("closing"))
        body = "".join(
            line(number, t, text, place, ids) for number, ((t, text), place) in enumerate(zip(lines, places), 1)
        )
        commit = (run or record.get("local") or {}).get("commit")
        which = (f" · run{number_of(run)}" if number_of(run) else "") + (f" · {esc(str(commit)[:7])}" if commit else "")
        # The buttons need the script, which shows them. One replays the run and, while it
        # plays, ends the replay: the end is the page as it is, with every step and every
        # line. The others are how the lines are laid out, which is the reader's choice.
        tools = (
            '<span class="run-term-tools" hidden>'
            f'<button type="button" class="run-tool" data-run-wrap aria-pressed="true" aria-label="Wrap long lines" title="Wrap long lines">{ICONS["wrap"]}</button>'
            f'<button type="button" class="run-tool" data-run-copy aria-label="Copy the lines as the run printed them" title="Copy the lines as the run printed them">{ICONS["copy"]}</button>'
            f'<button type="button" class="run-tool" data-run-full aria-pressed="false" aria-label="Full screen" title="Full screen">'
            f'<span class="run-when-small">{ICONS["full"]}</span><span class="run-when-full">{ICONS["small"]}</span></button></span>'
        )
        terminal = (
            '<div class="run-term"><div class="run-term-bar">'
            f'<button type="button" class="run-play" data-run-play hidden><span class="run-when-idle">{ICONS["play"]}</span>'
            f'<span class="run-when-playing">{ICONS["end"]}</span><span data-run-play-label>Replay</span></button>'
            f'<span class="run-term-title">What the run printed<span class="run-term-id">{which}</span></span>'
            f'<span class="run-clock" data-run-clock></span>{tools}'
            '<span class="run-progress" aria-hidden="true"><span data-run-progress></span></span></div>'
            f'<div class="run-term-body"><pre class="transcript" tabindex="0" role="region" aria-label="What the run printed">{body}</pre></div></div>'
        )
    stage = (
        f'<div class="run-stage"><ol class="run-tabs" aria-label="The steps of the run">{tabs}</ol>'
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
            f'SHA-256 of the lines: {short(data["sha256"])}. '
            f'The same record as a file: <a href="{up}api/v1/last-run.json"><code>api/v1/last-run.json</code></a>.</p>'
        )
    return (
        f'<section class="run" data-run="{ids}" aria-labelledby="{ids}the-last-run">{head}{stage}{below}{note}</section>'
    )


# ------------------------------------------------ a run without a record of its own (plain)


def steps_table(record):
    """The steps GitHub recorded, for a run that kept no account of its own."""
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


def plain(site, record, up, title="The last run", ids=""):
    """A run that kept no account of its own: what GitHub recorded, and the transcript if
    there is one."""
    kind, said = worked(record)
    facts = (
        ("Run", run_line(site, record)),
        ("Did it work", f'<span class="run-{kind}">{said}</span>'),
        ("What is blocking", listed(blocking(site, record, up))),
        ("What was in it", listed(contents(site, record, up))),
    )
    panel = '<dl class="panel run-facts">' + "".join(f"<div><dt>{label}</dt><dd>{value}</dd></div>" for label, value in facts) + "</dl>"
    table = steps_table(record)
    data, printed = record.get("transcript"), ""
    if data is not None:
        body = "".join(line(number, t, text, 0, ids) for number, (t, text) in enumerate(data["lines"], 1))
        printed = (
            f'<h3 id="{ids}what-the-run-printed">What the run printed</h3>'
            f'<p>{plural(len(data["lines"]), "line")}, exactly as the run printed them. SHA-256 of the lines: <code>{esc(data["sha256"])}</code>.</p>'
            f'<div class="run-term"><pre class="transcript" tabindex="0" role="region" aria-label="What the run printed">{body}</pre></div>'
        )
    return (
        f'<section class="run run-plain" aria-labelledby="{ids}the-last-run"><h2 class="run-title" id="{ids}the-last-run">{esc(title)}</h2>'
        + panel + (f'<h3 id="{ids}steps-of-the-run">Step by step</h3>{table}' if table else "") + printed + "</section>"
    )


def not_shown(record):
    """Why a page shows no run."""
    if record["state"] == "no run":
        return f"No {esc(lower(named(record)))} has run yet."
    return NOT_SHOWN[record["state"]]


def lower(name):
    return name[:1].lower() + name[1:]


def view(site, record, up, title, ids=""):
    """One run as a part of the page: the walk through it, or what GitHub recorded of it."""
    if record.get("summary") is None:
        return plain(site, record, up, title, ids)
    return showcase(site, record, up, title, ids)


def started(record):
    """The day a run began, in words, as markup."""
    at = (record.get("run") or record.get("local") or {}).get("started")
    return day(str(at)[:10], long=True) if moment(at) else ""


def last_run(site, up=""):
    """The block a prose page asks for with <!-- generated: last-run -->. Where the record
    also holds the last run that was made for a tag, the page holds both: the work as it
    stands, and the one that others should use. A switch, which the script shows, chooses
    between them; without the script the two stand one after the other."""
    record = site.last_run
    name = lower(named(record))
    if record["state"] != "read":
        return (
            '<section class="run run-plain" aria-labelledby="the-last-run">'
            f'<h2 class="run-title" id="the-last-run">The last {esc(name)}</h2>'
            f'<p class="list-none">{not_shown(record)}</p></section>'
        )
    script = f'<script src="{up}assets/replay.js" defer></script>' if record.get("summary") or (record.get("of_tag") or {}).get("summary") else ""
    of_tag = record.get("of_tag")
    if not of_tag:
        return view(site, record, up, f"The last {name}") + script
    made = record | of_tag | {"newer": None, "of_tag": None}
    tag = (made.get("summary") or {}).get("tag") or made["run"].get("branch") or ""
    buttons = (
        ("", f"Latest {name}", started(record)),
        (TAG_IDS, f"Latest tagged {name}", " · ".join(part for part in (esc(tag), started(made)) if part)),
    )
    switch = '<div class="run-switch" data-run-switch hidden role="group" aria-label="Which run is shown">' + "".join(
        f'<button type="button" class="run-switch-btn" data-run-view="{ids}" aria-pressed="{"true" if not ids else "false"}">'
        f"<strong>{esc(label)}</strong><span>{about}</span></button>"
        for ids, label, about in buttons
    ) + "</div>"
    return (
        switch
        + f'<div class="run-view" data-run-view-of="">{view(site, record, up, f"The last {name}")}</div>'
        + f'<div class="run-view" data-run-view-of="{TAG_IDS}">{view(site, made, up, f"The last tagged {name}", TAG_IDS)}</div>'
        + script
    )


# ------------------------------------------------- what was published, and the files of a run


def megabytes(size):
    return f"{size / 1e6:,.1f} MB" if isinstance(size, (int, float)) and not isinstance(size, bool) else ""


def package_rows(record):
    """The files the last run made, each with where it can be had:
    [{label, name, size, sha256, same, url}]. `url` is a file of the newest tagged build with
    the same name, or None: a file that no tagged build holds can't be downloaded."""
    account = record.get("summary") or {}
    newest = (record.get("releases") or [{}])[0]
    held = {asset.get("name"): asset.get("url") for asset in newest.get("assets") or ()}
    return [
        {
            "label": file["label"], "name": file["name"], "size": megabytes(file["bytes"]),
            "sha256": file.get("sha256"), "same": file.get("same"), "url": held.get(file["name"]),
        }
        for file in account.get("files") or ()
    ]


def packages(site, up=""):
    """The block <!-- generated: build-files -->: the builds that have a tag, with the
    files each holds, and the files of the last run with their size, their checksum and
    whether they can be downloaded. Nothing is offered that no tagged build holds."""
    record = site.last_run
    if record["state"] != "read":
        return ('<div class="packages" id="build-files" data-packages><p class="list-none">'
                f"{TAG['not read']}</p></div>")
    releases = record.get("releases") or []
    if releases:
        listed_ = '<ul class="plain releases">' + "".join(
            f'<li><strong><code>{esc(release["tag"])}</code></strong> <span class="quiet">· {day(release["published"], long=True)}</span> · '
            f'{ext(release["url"], TAG["on GitHub"])}'
            + "".join(f'<br>{ext(asset["url"], "<code>" + esc(asset["name"]) + "</code>")} <span class="quiet">{megabytes(asset["size"])}</span>'
                      for asset in release["assets"])
            + "</li>"
            for release in releases
        ) + "</ul>"
    else:
        listed_ = f'<p class="list-none">{TAG["none yet"]}</p>'
    rows = package_rows(record)
    table = ""
    if rows:
        run = record.get("run")
        head = ("File", "For", "Size", "SHA-256", "Where")
        lines = ""
        for row in rows:
            where = ext(row["url"], "Download") if row["url"] else TAG["where not"]
            read = "" if row["same"] is not False else ' <span class="run-no"><strong>did not read back the same</strong></span>'
            checksum = short(row["sha256"]) if row["sha256"] else ""
            cells = (f'<code>{esc(row["name"])}</code>{read}', esc(row["label"]), esc(row["size"]), checksum, where)
            lines += '<tr role="row">' + "".join(
                f'<td role="cell" data-label="{label}">{cell}</td>' for label, cell in zip(head, cells)
            ) + "</tr>"
        started = (run or record.get("local") or {}).get("started")
        which = (f"run{number_of(run)}, " if number_of(run) else "") + when(started)
        table = (
            f"<p>The files of the last run ({which}), each read back after it was written:</p>"
            '<div class="table-wrap"><table role="table" class="cols-5 key-short"><thead role="rowgroup"><tr role="row">'
            + "".join(f'<th role="columnheader" scope="col">{label}</th>' for label in head)
            + f'</tr></thead><tbody role="rowgroup">{lines}</tbody></table></div>'
        )
    return f'<div class="packages" id="build-files" data-packages>{listed_}{table}</div>'


def rail_box(site, up=""):
    """The same files, small, beside the text under "On this page". The script shows the
    box once the reader has scrolled past that part; without the script it is always there."""
    record = site.last_run
    rows = package_rows(record) if record["state"] == "read" else []
    if not rows:
        return ""
    newest = (record.get("releases") or [{}])[0]
    title = TAG["box of"].format(tag=esc(newest["tag"])) if newest.get("tag") else TAG["box"]
    items = "".join(
        f'<li><span class="downloads-name">{esc(row["label"])}</span><span class="quiet">{esc(row["size"])}</span>'
        + (ext(row["url"], "Download") if row["url"] else f'<span class="quiet">{TAG["where not"]}</span>')
        + "</li>"
        for row in rows
    )
    return (
        '<div class="downloads" data-show-after="build-files">'
        f'<p class="card-label">{title}</p><ul>{items}</ul>'
        f'<a class="arrow" href="#build-files">{TAG["about"]}</a></div>'
    )


def public_record(record):
    """The record as a file of the site: as it was read."""
    return record
