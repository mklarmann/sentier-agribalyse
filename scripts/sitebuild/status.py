"""Where a finding or a contribution stands, in four sizes of one idea.

    path_with_counts   the five steps with what happens and how many findings wait after each
    finding_tracker    the same five steps for one finding, each with its dated evidence
    status_cell        a five-segment meter with the status in words, on a row of a list
    chips              the statuses as links that filter a list

A step is shown as done only when the record holds its evidence (triage.steps). A step
without evidence that a later step has passed says "not recorded".
"""

import community

from .text import day, esc, thousands

# (evidence key, name of the step, what happens). {p} is the provider's name, {a_p} the name
# with its article ("A ..." or "An ...").
# The feedback is continuous: the path ends when a release of the provider covers the point,
# and nothing here frames it as waiting for a release.
STEPS = (
    ("reported", "Measured", "Someone measures it on {p}'s files."),
    ("repeated", "Repeated", "A second person repeats the measurement."),
    ("sent", "Reported to {p}", "The finding is reported to {p}."),
    ("answer", "Answered by {p}", "{p} answers."),
    ("fixed_in", "Resolved", "{a_p} release covers the point."),
)
# The status of the findings that wait after each step, and the words under their count.
AFTER = {
    "reported": ("filed", "needs a second measurement", "need a second measurement"),
    "repeated": ("confirmed", "repeated, not yet reported", "repeated, not yet reported"),
    "sent": ("sent", "reported, no answer yet", "reported, no answer yet"),
    "answer": ("answered", "answered by {p}", "answered by {p}"),
    "fixed_in": ("fixed", "resolved", "resolved"),
}
# What a step that is not done says under its name.
WAITING = {
    "repeated": "a second person is wanted",
    "sent": "not yet reported",
    "answer": "no answer yet",
    "fixed_in": "not yet",
}
SAID = {"done": "done", "now": "current", "help": "current, help wanted", "todo": "not yet",
        "unrecorded": "not recorded", "plain": ""}
SEGMENT = {"done": "on", "now": "now", "help": "help", "unrecorded": "gap", "fail": "fail"}
# A typical finding of each status, for the small meter beside a filter.
TYPICAL = {
    "filed": ("done", "help", "todo", "todo", "todo"),
    "confirmed": ("done", "done", "now", "todo", "todo"),
    "sent": ("done", "done", "done", "now", "todo"),
    "answered": ("done", "done", "done", "done", "now"),
    "fixed": ("done", "done", "done", "done", "done"),
}
OFF = '<span class="meter off" aria-hidden="true"></span>'
CONTRIBUTION_STATES = ("proposed", "testing", "reviewing", "accepted")


def meter(states):
    """One segment per step. Decoration: the words beside it say the same."""
    cells = "".join(f'<i class="{SEGMENT[s]}"></i>' if s in SEGMENT else "<i></i>" for s in states)
    return f'<span class="meter" aria-hidden="true">{cells}</span>'


def path(steps, label, modifier=""):
    """The tracker. steps: (state, name, detail html, extra html, key)."""
    items = ""
    for n, (state, name, detail, extra, key) in enumerate(steps):
        follows = n + 1 < len(steps) and steps[n + 1][0] != "todo"
        items += (
            f'<li class="is-{state}{" is-linked" if follows else ""}" data-step="{esc(key)}"'
            + (' aria-current="step"' if state in ("now", "help") else "")
            + f'><span class="path-dot" aria-hidden="true">{n + 1 if state == "plain" else ""}</span>'
            + f'<span class="path-name">{name}'
            + (f'<span class="visually-hidden"> ({SAID[state]})</span>' if SAID[state] else "") + "</span>"
            + (f'<span class="path-detail">{detail}</span>' if detail else "")
            + extra + "</li>"
        )
    classes = f"path of-{len(steps)} {modifier}".strip()
    return f'<ol class="{classes}" aria-label="{esc(label)}">{items}</ol>'


def dated(block, what, text=None):
    """The date of a piece of evidence as a link to where it is recorded."""
    shown = text or day(block.get("date")) or "date not recorded"
    if not block.get("url"):
        return shown
    return f'<a href="{esc(block["url"])}">{shown}<span class="visually-hidden">: {what}</span></a>'


def step_detail(site, f, step, up):
    key, state, block = step["key"], step["state"], step["block"]
    if state == "unrecorded":
        return "not recorded"
    if state == "todo":
        return ""
    if state != "done":
        if key == "repeated" and block:  # repeated, with a different result
            return dated(block, "what the second person got") + ": not reproduced"
        return WAITING[key]
    if key == "reported":
        return dated(block, "where it was reported")
    if key == "repeated":
        return dated(block, "what the second person got") + ", by a second person"
    if key == "sent":
        return f'<a href="{up}feedback/{esc(block["batch"])}.html">{day(block["date"])}<span class="visually-hidden">: the report it was part of</span></a>'
    if key == "answer":
        outcome = community.OUTCOMES[block["outcome"]]["label"].lower()
        return dated(block, f"where {site.provider}'s answer is recorded") + f" · {esc(outcome)}"
    return f'in {esc(site.release_name(block["release"]))} · {dated(block, "where this is recorded")}'


def finding_tracker(site, f, up=""):
    """The five steps for one finding, then its status in words and one sentence about it."""
    p = site.provider
    off = bool(f["closed"])
    steps = [
        (step["state"], esc(name.format(p=p)), step_detail(site, f, step, up), "", step["key"])
        for step, (_, name, _) in zip(f["steps"], STEPS)
    ]
    return (
        f'<section class="tracker{" is-off" if off else ""}" aria-label="Where this finding stands">'
        + path(steps, "The path of this finding")
        + f'<p class="stage-line"><strong>{esc(site.label(f["stage"]))}.</strong> '
        f'{esc(community.status_description(f["stage"], p))}</p></section>'
    )


def status_cell(site, f):
    """A row's status: the words, the meter, and what stands beside the status (answer, patch)."""
    label = esc(site.label(f["stage"]))
    if f["closed"]:
        return (f'<div class="record-stage off"><span class="stage-label">{label}</span>'
                f'<span class="stage-sub">{OFF}<span class="tag">off the path</span></span></div>')
    tags = ""
    if f["answer"]:
        tags += f'<span class="tag">{esc(community.OUTCOMES[f["answer"]["outcome"]]["label"].lower())}</span>'
    tags += "".join(f'<span class="tag">patch {esc(x["id"])}</span>' for x in f["patches"])
    return (
        f'<div class="record-stage{" help" if f["stage"] == "filed" else ""}"><span class="stage-label">{label}</span>'
        f'<span class="stage-sub">{meter(s["state"] for s in f["steps"])}{tags}</span></div>'
    )


def chips(site, counts, href="#stage-{}", label="Filter by status"):
    """The statuses as links. Without the script a link filters the rows on the page
    (the stylesheet hides the others); with it, the list script takes the click."""
    out = f'<div class="chips" role="group" aria-label="{esc(label)}">'
    for status in community.statuses(site.provider):
        key, n = status["key"], counts.get(status["key"], 0)
        if key == "not-a-defect":
            out += '<span class="chips-gap">Off the path</span>'
        mark = meter(TYPICAL[key]) if key in TYPICAL else OFF
        out += (
            f'<a class="chip{"" if n else " none"}" href="{href.format(key)}" data-filter="{key}">'
            f'{mark}{esc(status["label"])} <b>{thousands(n)}</b></a>'
        )
    return out + "</div>"


def path_with_counts(site, up=""):
    """The five steps with the number of findings that wait after each; each number is a
    link to those findings. Then the two statuses off the path."""
    p, counts = site.provider, site.triage["counts"]
    steps = []
    for key, name, text in STEPS:
        stage, one, many = AFTER[key]
        n = counts.get(stage, 0)
        caption = esc((one if n == 1 else many).format(p=p))
        box = f'<span class="path-desc">{esc(text.format(p=p, a_p=community.with_article(p)))}</span>' + (
            f'<a class="path-count{" help" if stage == "filed" else ""}" href="{up}findings.html#stage-{stage}">'
            f"<strong>{thousands(n)}</strong> <span>{caption}</span></a>"
            if n else f'<span class="path-count none"><strong>0</strong> <span>{caption}</span></span>'
        )
        steps.append(("plain", esc(name.format(p=p)), "", box, key))
    info, gone = counts.get("not-a-defect", 0), counts.get("withdrawn", 0)

    def off(n, key, words):
        text = f"<strong>{thousands(n)}</strong> {words}"
        return f'<a href="{up}findings.html#stage-{key}">{text}</a>' if n else text

    return (
        f'<div class="card pipeline">{path(steps, "How it works", "counts")}'
        f'<p class="path-off"><span>Off the path</span> {off(info, "not-a-defect", "for information")} · '
        f'{off(gone, "withdrawn", "withdrawn")}</p></div>'
    )


def vocabulary(site):
    """Every status with its meter and the one sentence that is true of every finding that has it."""
    rows = ""
    for status in community.statuses(site.provider):
        mark = meter(TYPICAL[status["key"]]) if status["key"] in TYPICAL else OFF
        rows += f'<div><dt>{mark}{esc(status["label"])}</dt><dd>{esc(status["description"])}</dd></div>'
    return f'<dl class="panel vocabulary">{rows}</dl>'


def contribution_meter(status):
    if status not in CONTRIBUTION_STATES:
        return OFF
    at = CONTRIBUTION_STATES.index(status)
    if status == CONTRIBUTION_STATES[-1]:
        return meter(["done"] * len(CONTRIBUTION_STATES))
    return meter("done" if n < at else "now" if n == at else "todo" for n in range(len(CONTRIBUTION_STATES)))
