"""A contribution as a row of a list, the contributions list, and the contribution page."""

import re

import community

from . import status
from .prose import render
from .text import esc, ext, link_label, number_word, plural, words

RETAINED = {"ask": "Request", "objection": "Objection", "earlier-interpretation": "Earlier reading"}
PILL = {"passed": ("ok", "Passed"), "failed": ("fail", "Failed")}


def checks(record):
    """The required checks with their latest result: [(name, result or None)]."""
    results = {}
    for run in record["runs"]:
        for check in run.get("checks", []):
            results[check["id"]] = check
    return [(name, results.get(name)) for name in record["required_checks"]]


def tally(record):
    """(passed, failed, not run) of the required checks."""
    found = [(r or {}).get("status") for _, r in checks(record)]
    passed, failed = found.count("passed"), found.count("failed")
    return passed, failed, len(found) - passed - failed


def tally_words(record):
    passed, failed, idle = tally(record)
    parts = [f"{passed} passed"] + ([f"{failed} failed"] if failed else []) + ([f"{idle} not run"] if idle else [])
    return " · ".join(parts)


def check_bar(record):
    cells = "".join(
        f'<i class="{ {"passed": "on", "failed": "fail"}.get((r or {}).get("status"), "") }"></i>'
        for _, r in checks(record)
    )
    return f'<span class="meter checks-bar" aria-hidden="true">{cells}</span>'


def kind_words(site, c):
    kind = community.CONTRIBUTION_CLASS[c["class"]]
    group = community.CONTRIBUTION_GROUPS[kind["group"]].format(provider=site.provider)
    return kind["label"], group[:1].lower() + group[1:]


def state_cell(c):
    label = esc(c["status"].capitalize())
    if c["status"] not in status.CONTRIBUTION_STATES:
        return f'<div class="record-stage off"><span class="stage-label">{label}</span><span class="stage-sub">{status.OFF}</span></div>'
    return (f'<div class="record-stage"><span class="stage-label">{label}</span>'
            f'<span class="stage-sub">{status.contribution_meter(c["status"])}</span></div>')


def contribution_row(site, c, up=""):
    cid = esc(c["id"])
    label, group = kind_words(site, c)
    approvals = len(c["approvals"])
    issue = ext(f'{site.repo}/issues/{int(c["issue"])}', f'Issue #{int(c["issue"])}') if c.get("issue") else ""
    return (
        f'<li class="record" data-stage="{esc(c["status"])}">'
        f'<span class="record-id">{cid}</span>'
        f'<div class="record-main"><a class="record-title" href="{up}contributions/{cid}.html" dir="auto">{esc(c["title"])}</a>'
        f'<p class="record-meta"><span class="meta-what">{esc(label)} · {esc(group)}</span></p></div>'
        + state_cell(c)
        + f'<div class="record-thread"><span class="thread-line">{check_bar(c)}<span>{tally_words(c)}</span></span>'
        f'<span class="quiet">{"no approvals yet" if not approvals else plural(approvals, "approval")}</span>{issue}</div></li>'
    )


def contributions_list(site, up=""):
    """Every contribution as a row, with a search and a status filter the list script runs
    on the rows of the page."""
    present = [s for s in list(status.CONTRIBUTION_STATES) + ["rejected", "superseded"]
               if any(c["status"] == s for c in site.contributions)]
    options = '<option value="">All statuses</option>' + "".join(
        f'<option value="{esc(s)}">{esc(s.capitalize())}</option>' for s in present
    )
    total = len(site.contributions)
    return (
        '<div class="filter" id="filter"><form class="filter-row" id="controls" role="search" hidden>'
        '<label class="field grow"><span>Search</span><input id="q" name="q" type="search" '
        'placeholder="Title, type or word" autocomplete="off" spellcheck="false"></label>'
        f'<label class="field"><span>Status</span><select id="status" name="status">{options}</select></label></form>'
        f'<p class="filter-count"><span id="count" role="status">{plural(total, "contribution")}</span></p></div>'
        '<div class="listing of-contributions"><div class="records-head" aria-hidden="true"><span>No.</span>'
        "<span>Contribution</span><span>Status</span><span>Checks</span></div>"
        f'<ul class="records" id="list" data-total="{total}" data-page="50" data-noun="contribution">'
        + "".join(contribution_row(site, c, up) for c in site.contributions)
        + "</ul></div>"
        '<p class="list-none" id="none" hidden>No contribution matches. '
        '<button type="button" class="linklike" id="clear">Clear the search and the filter</button></p>'
        '<p class="list-more"><button type="button" class="button" id="more" hidden>Show 50 more</button></p>'
        f'<script src="{up}assets/list.js" defer></script>'
    )


def tracker(site, c):
    """Proposed, testing, reviewing, accepted: where a contribution stands and what it has."""
    states = status.CONTRIBUTION_STATES
    off = c["status"] not in states
    at = len(states) if c["status"] == states[-1] else (-1 if off else states.index(c["status"]))
    passed, failed, idle = tally(c)
    total = passed + failed + idle
    approvals = len(c["approvals"])
    detail = {
        "testing": f"{passed} of {total} checks passed",
        "reviewing": "no approvals yet" if not approvals else plural(approvals, "approval"),
    }
    steps = [
        ("done" if n < at else "now" if n == at else "todo", s.capitalize(), detail.get(s, ""), "", s)
        for n, s in enumerate(states)
    ]
    summary = (
        f"{passed} of {total} required checks passed"
        + (f", {failed} failed" if failed else "") + (f", {idle} not run" if idle else "") + ". "
        + ("No reviewers are named yet." if not c["required_reviewers"] else
           f'{number_word(approvals).capitalize()} of {plural(len(c["required_reviewers"]), "named reviewer")} '
           f'{"has" if approvals == 1 else "have"} approved.')
    )
    return (
        f'<section class="tracker{" is-off" if off else ""}" aria-label="Where this contribution stands">'
        + status.path(steps, "The path of this contribution")
        + f'<p class="stage-line"><strong>{esc(c["status"].capitalize())}.</strong> {summary}</p></section>'
    )


def release_words(site, baseline):
    """A record names a release with the provider before its id; the site calls it by its name."""
    release = str(baseline.get("release", ""))
    prefix = site.provider + "-"
    return site.release_name(release[len(prefix):] if release.startswith(prefix) else release)


def code_words(site, layer):
    revision = str(layer.get("implementation_revision") or "")
    if re.fullmatch(r"[0-9a-f]{40}", revision):
        revision = revision[:12]
    if layer.get("implementation_url"):
        at = f' <span class="quiet">at <code>{esc(revision)}</code></span>' if revision and ":" not in revision else ""
        return ext(layer["implementation_url"], esc(link_label(layer["implementation_url"], site.repo))) + at
    return "Not public yet. Files are identified by checksum in the record."


def assessment(site, c, up):
    """The longer notes on one contribution, from the Markdown files site/config.json names."""
    out = ""
    for source in site.config.get("assessments", {}).get(c["id"], []):
        path = site.root / source
        if path.is_file():
            body, _ = render(site, path.read_text(), source, up, shift=2)
            out += f'<section class="assessment">{body}</section>'
    return f'<h2 id="assessment">Assessment</h2>{out}' if out else ""


def contribution_page(site, c):
    up, cid = "../", esc(c["id"])
    label, group = kind_words(site, c)
    rows = ""
    for name, r in checks(c):
        tone, said = PILL.get((r or {}).get("status"), ("todo", "Not run"))
        ran = r and r.get("status") in PILL and r.get("evidence_url")
        evidence = ext(r["evidence_url"], f'run record<span class="visually-hidden"> for {esc(words(name).lower())}</span>') if ran else ""
        rows += (f'<li><span class="check-name">{esc(words(name))} <code>{esc(name)}</code></span>'
                 f'<span class="pill {tone}">{said}</span><span class="check-link">{evidence}</span></li>')
    layer, links = c["layer"], []
    # An assessment file is shown on this page: a link to the same file would lead back here.
    shown = tuple("/" + source for source in site.config.get("assessments", {}).get(c["id"], []))
    for url in ([f'{site.repo}/issues/{int(c["issue"])}'] if c.get("issue") else []) + list(c["evidence"]):
        if url not in links and not (shown and url.endswith(shown)):
            links.append(url)
    button = ""
    if c.get("issue"):
        button = ext(links.pop(0), "Discuss on GitHub", "button primary block ext")
    approvals, reviewers = len(c["approvals"]), len(c["required_reviewers"])
    rail = (
        '<section class="card" aria-labelledby="discussion"><h2 class="card-label" id="discussion">Discussion and evidence</h2>'
        + button
        + ('<ul class="links">' + "".join(f"<li>{ext(u, esc(link_label(u, site.repo)))}</li>" for u in links) + "</ul>"
           if links else "" if button else '<p class="card-meta">No discussion is recorded.</p>')
        + "</section>"
        '<section class="card" aria-labelledby="review"><h2 class="card-label" id="review">Review</h2>'
        f'<p>{"Reviewers are not yet named." if not reviewers else plural(reviewers, "reviewer") + " named in the record."}</p>'
        f'<p class="card-meta">Approvals: {"none yet" if not approvals else approvals}</p></section>'
    )
    retained = "".join(
        f'<li><strong>{RETAINED.get(x["kind"], esc(words(x["kind"])))}.</strong> {esc(x["text"])} '
        f'{ext(x["evidence_url"], esc(link_label(x["evidence_url"], site.repo)))}</li>'
        for x in c.get("retained", [])
    )
    main = ""
    if c.get("next_action"):
        role = f'<p class="note">Taken by: {esc(c["review_role"])}</p>' if c.get("review_role") else ""
        main += f'<dl class="panel"><div><dt>Next step</dt><dd>{esc(c["next_action"])}{role}</dd></div></dl>'
    source = f'{site.source_repo}/blob/{site.ref}/{c.path}'
    main += (
        f'<h2>Required checks</h2><ul class="checks">{rows}</ul>'
        + (f"<h2>What the checks cover</h2><p>{esc(c['validation_scope'])}</p>" if c.get("validation_scope") else "")
        + (f"<h2>Also on record</h2><ul>{retained}</ul>" if retained else "")
        + assessment(site, c, up)
        + f'<p class="source">Source of this page: {ext(source, "record " + cid + ".json on GitHub")}</p>'
    )
    body = (
        '<div class="wrap page">'
        f'<header class="record-head"><nav class="crumb" aria-label="Breadcrumb"><a href="{up}contributions.html">Contributions</a> '
        f'<span aria-hidden="true">/</span> <span aria-current="page">{cid}</span></nav>'
        f'<h1 dir="auto">{esc(c["title"])}</h1><dl class="facts">'
        f'<div><dt>Type</dt><dd>{esc(label)} <span class="quiet">· {esc(group)}</span></dd></div>'
        f'<div><dt>Based on</dt><dd>{esc(release_words(site, c["baseline"]))}</dd></div>'
        f'<div><dt>Code or files</dt><dd>{code_words(site, layer)}</dd></div></dl></header>'
        + tracker(site, c)
        + f'<div class="with-rail"><aside class="rail" aria-label="Discussion and review">{rail}</aside>'
        f'<div class="prose">{main}</div></div></div>'
    )
    return site.shell(
        f'{c["id"]} · {c["title"]}', body, "contributions.html", up=up, page=f'contributions/{c["id"]}.html',
        description=f'{c["id"]}: {c["title"]}. Status: {c["status"]}.',
    )
