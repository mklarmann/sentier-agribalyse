"""A finding as a row of a list, the findings list with its index, and the finding page."""

import community

from . import status
from .prose import record_text
from .text import comments, day, esc, ext, link_label, plain, plural, shorten, thousands

PAGE = 50  # rows the list page ships as HTML, and rows each "Show more" adds
RETAINED = {"ask": "Request", "objection": "Objection", "earlier-interpretation": "Earlier reading"}
ROLE_WORDS = {"affected": "affected", "named": "named"}
STATE_LETTER = {"done": "d", "now": "n", "help": "h", "unrecorded": "g", "todo": "t"}
SORTS = (("changed", "Last change"), ("number", "Number"), ("waiting", "Longest waiting"))


# ------------------------------------------------------------------------------ row


def concerns_text(site, f):
    """What a finding is about, as one plain line: its subject datasets, then its scope."""
    parts = [
        f'{int(d["code"])} {d["name"]} ({d["location"]})'
        for d in f["datasets"]
        if d.get("role", "subject") == "subject"
    ]
    if f["scope"].strip():
        parts.append(plain(record_text(site, f["scope"], inline=True)))
    return "; ".join(parts)


def discussion(site, f):
    """Where a finding is discussed: (url, label, comments or None)."""
    issue = f["tracker"]
    if f["issue"]:
        url = issue["url"] if issue else f'{site.repo}/issues/{int(f["issue"])}'
        return url, f'Issue #{int(f["issue"])}', issue["comments"] if issue else None
    if f["threads"]:
        return f["threads"][0], link_label(f["threads"][0], site.repo), None
    return None, "", None


def thread_cell(site, f):
    url, label, count = discussion(site, f)
    link = ext(url, esc(label)) if url else ""
    said = f'<span class="comments">{comments(count)}</span>' if count is not None else ""
    changed = f'<span class="quiet">changed {day(f["changed"])}</span>' if f["changed"] else ""
    return f'<div class="record-thread"><span class="thread-line">{link}{said}</span>{changed}</div>'


def finding_row(site, f, up="", extra=""):
    """One finding as a row: number, what it is, where it stands, where it is discussed.
    The title is the only link to the finding; the discussion link stays its own target."""
    rid = esc(f["id"])
    releases = community.release_names(f, site.records_config) if f["releases"] else ""
    return (
        f'<li class="record" data-stage="{esc(f["stage"])}">'
        f'<span class="record-id">{rid}</span>'
        f'<div class="record-main"><a class="record-title" href="{up}findings/{rid}.html" dir="auto">{esc(f["title"])}</a>'
        f'<p class="record-meta"><span class="meta-what">{esc(shorten(concerns_text(site, f)))}</span>'
        + (f'\u00a0· <span class="meta-release">{esc(releases)}</span>' if releases else "")
        + f"</p>{extra}</div>"
        + status.status_cell(site, f) + thread_cell(site, f) + "</li>"
    )


def rows(site, findings, up="", limit=None, more="", empty="", extra=None):
    """A list of findings as rows. Above `limit` the rest is one link to the filtered list."""
    if not findings:
        return f'<p class="list-none">{empty}</p>' if empty else ""
    shown = findings[:limit] if limit else findings
    out = '<ul class="records">' + "".join(
        finding_row(site, f, up, extra(f) if extra else "") for f in shown
    ) + "</ul>"
    if limit and len(findings) > limit and more:
        out += f'<p class="list-more"><a class="arrow" href="{more}">All {thousands(len(findings))} in the findings list</a></p>'
    return out


def recent(site):
    """Every finding, the most recently changed first: the order of the list and of its index."""
    return sorted(
        site.triage["findings"],
        key=lambda f: (f["changed"] or "", community.finding_number(f)),
        reverse=True,
    )


# ----------------------------------------------------------------------------- list


def list_index(site):
    """The compact index the list script loads on first use of search, a filter, a sort or
    "show more": one array per finding, in the order of the page. Not part of api/v1."""
    config = site.records_config
    releases = [r["id"] for r in config["releases"]]
    statuses = [s["key"] for s in community.STATUSES]
    kinds, outcomes = list(community.KINDS), list(community.OUTCOMES)
    entries = []
    for f in recent(site):
        url, label, count = discussion(site, f)
        full = concerns_text(site, f)
        shown = shorten(full)
        more = [full] if shown != full else []
        more += [f'{d["code"]} {d["name"]} {d["location"]}' for d in f["datasets"] if d.get("role", "subject") != "subject"]
        more += [f'patch {x["id"]} {x["slug"]}' for x in f["patches"]]
        entries.append([
            community.finding_number(f),
            f["title"],
            shown,
            " ".join(more),
            [int(d["code"]) for d in f["datasets"]],
            [releases.index(r) for r in f["releases"] if r in releases],
            statuses.index(f["stage"]),
            "" if f["closed"] else "".join(STATE_LETTER[s["state"]] for s in f["steps"]),
            outcomes.index(f["answer"]["outcome"]) if f["answer"] else -1,
            [x["id"] for x in f["patches"]],
            label,
            url or "",
            -1 if count is None else count,
            f["changed"] or "",
            f["waiting_since"] or "",
            kinds.index(f["kind"]),
        ])
    return {
        "schema": "sentier-bafu/list-index/1",
        "note": "For the findings list of the site. Tools read api/v1/findings.json instead.",
        "columns": ["number", "title", "concerns", "more", "codes", "releases", "status", "steps", "outcome",
                    "patches", "thread", "thread_url", "comments", "changed", "waiting_since", "kind"],
        "statuses": [[s["key"], s["label"]] for s in community.statuses(site.provider)],
        "releases": [[r["id"], r["name"]] for r in config["releases"]],
        "kinds": [[key, community.KINDS[key]["label"]] for key in kinds],
        "outcomes": [community.OUTCOMES[key]["label"].lower() for key in outcomes],
        "rows": entries,
    }


def select(name, label, options, classes="field"):
    choices = "".join(f'<option value="{esc(value)}">{esc(text)}</option>' for value, text in options)
    return f'<label class="{classes}"><span>{label}</span><select id="{name}" name="{name}">{choices}</select></label>'


def findings_list(site, up=""):
    """The findings list: status links, search and filters, the most recently changed rows.

    The page holds PAGE rows as HTML. The script loads the index on first use and keeps the
    state in the address. Without the script the rows and the status links still work.
    """
    p, counts, config = site.provider, site.triage["counts"], site.records_config
    ordered = recent(site)
    total = len(ordered)
    anchors = "".join(f'<span class="status-target" id="stage-{s["key"]}"></span>' for s in community.STATUSES)
    statuses = [("", "All statuses")] + [
        (s["key"], f'{s["label"]} ({thousands(counts.get(s["key"], 0))})') for s in community.statuses(p)
    ]
    controls = (
        '<form class="filter-row" id="controls" role="search" hidden>'
        '<label class="field grow"><span>Search</span><input id="q" name="q" type="search" '
        f'placeholder="{"Dataset code, name or word" if site.code_pattern else "Dataset name or word"}" autocomplete="off" spellcheck="false"></label>'
        + select("status", "Status", statuses, "field for-status")
        # On a narrow screen the four fields below open with this button; on a wide one they are always there.
        + '<button type="button" class="button more-filters" id="more-filters" aria-expanded="false">More filters</button>'
        + select("release", f"{esc(p)} release", [("", "All releases")] + [(r["id"], r["name"]) for r in config["releases"]], "field extra")
        + select("kind", "Kind", [("", "All kinds")] + [(k, v["label"]) for k, v in community.KINDS.items()], "field extra")
        + (select("patch", "Community patch", [("", "With or without"), ("1", "Has a patch")], "field extra")
           if (site.patches or {}).get("patches") else "")
        + select("sort", "Sort by", SORTS, "field extra")
        + "</form>"
    )
    unlisted = ""
    if site.triage["unlisted"]:
        # Number and link only: an issue's title is not reviewed text.
        links = ", ".join(ext(i["url"], f'#{int(i["number"])}') for i in site.triage["unlisted"])
        n = len(site.triage["unlisted"])
        unlisted = (
            f'<p class="unlisted" id="unlisted">{plural(n, "report has", "reports have")} an issue but no record yet: '
            f"{links}. Each gets a number when its record is written.</p>"
        )
    release_links = ", ".join(
        f'<a href="{up}releases/{esc(r["id"])}.html">{esc(r["name"])}</a>' for r in config["releases"]
    )
    return (
        anchors
        + f'<div class="filter" id="filter">{status.chips(site, counts)}{controls}'
        f'<p class="filter-count"><span id="count" role="status">{plural(total, "finding")}</span> '
        '<a class="arrow" id="dataset" href="#list" hidden>All about this dataset</a></p></div>'
        + unlisted
        + '<div class="listing"><div class="records-head" aria-hidden="true"><span>No.</span><span>Finding</span>'
        "<span>Status</span><span>Discussion</span></div>"
        f'<ul class="records" id="list" data-index="{up}findings/index.json" data-total="{total}" data-page="{PAGE}" '
        f'data-base="{up}" data-noun="finding"' + (f' data-code="{esc(site.code_pattern)}"' if site.code_pattern else "") + ">"
        + "".join(finding_row(site, f, up) for f in ordered[:PAGE])
        + "</ul></div>"
        '<p class="list-none" id="none" hidden>No finding matches. '
        '<button type="button" class="linklike" id="clear">Clear the search and the filters</button></p>'
        f'<p class="list-more"><button type="button" class="button" id="more" hidden>Show {PAGE} more</button></p>'
        '<noscript><p class="note">Search, filters and sorting need JavaScript. Without it this page shows the '
        f"{min(PAGE, total)} most recently changed of {plural(total, 'finding')}, and a status link above filters those. "
        f'Every finding is in the <a href="{up}ledger.md">findings table</a> and in '
        f'<a href="{up}api/v1/findings.json">findings.json</a>; the page of each {esc(p)} release lists its findings '
        f"by status: {release_links}.</p></noscript>"
        f'<script src="{up}assets/list.js" defer></script>'
    )


# ----------------------------------------------------------------------------- page


def dataset_line(site, d, up):
    code = int(d["code"])
    return f'<a href="{up}datasets/{code}.html">{code}</a> {esc(d["name"])} ({esc(d["location"])})'


def other_datasets(site, f, up):
    """The datasets a finding names without being about them, by what they have to do with it."""
    out = ""
    for role, meaning in community.DATASET_ROLES.items():
        found = [d for d in f["datasets"] if d.get("role", "subject") == role]
        if role != "subject" and found:
            out += (f'<p class="note">{esc(meaning)}</p><ul class="plain">'
                    + "".join(f"<li>{dataset_line(site, d, up)}</li>" for d in found) + "</ul>")
    return f"<h2>Other datasets named</h2>{out}" if out else ""


def discussion_card(site, f, up):
    """Beside the text: the discussion, with the one primary button of the page."""
    issue = f["tracker"]
    url, label, count = discussion(site, f)
    rest = f["threads"] if f["issue"] else f["threads"][1:]
    if f["issue"]:
        button = ext(url, "Discuss on GitHub", "button primary block ext")
        meta = esc(label)
        if issue:
            meta += f' · {comments(count)} · last activity {day(issue["updated"])}'
            meta += " · closed" if issue["state"] == "closed" else ""
    elif url:
        button = ext(url, "Open the discussion", "button primary block ext")
        meta = f"{esc(label)}. This finding has no issue in this repository."
    else:
        button, meta = "", "No discussion is recorded."
    others = "".join(f'<li>{ext(u, esc(link_label(u, site.repo)))}</li>' for u in rest)
    card = (
        '<section class="card" aria-labelledby="discussion"><h2 class="card-label" id="discussion">Discussion</h2>'
        + button + f'<p class="card-meta">{meta}</p>'
        + (f'<p class="card-also">Also discussed in</p><ul class="links">{others}</ul>' if others else "")
        + "</section>"
    )
    if f["stage"] == "filed":
        where = f'in {ext(url, esc(label.replace("Issue", "issue")))}' if url else "in its discussion"
        card += (
            '<section class="card help" aria-labelledby="repeat"><h2 class="card-label" id="repeat">Can you repeat this measurement?</h2>'
            f"<p>Measure it on {esc(site.provider)}'s release files and write what you got {where}. "
            "A different result is as useful as the same one.</p>"
            f'<a class="arrow" href="{up}take-part.html">How to take part</a></section>'
        )
    return card


def answer_block(site, f, up):
    answer = f["answer"]
    if not answer:
        return ""
    outcome = community.OUTCOMES[answer["outcome"]]
    return (
        f'<section class="answer" aria-labelledby="answer"><h2 class="card-label" id="answer">{esc(site.provider)}\'s answer '
        f'<span>· {day(answer["date"])} · {esc(outcome["label"].lower())}</span></h2>'
        f'<div class="answer-text">{record_text(site, answer["summary"], up=up, link_ids=True, own=f["id"])}</div>'
        f'<p class="answer-foot">Recorded in {ext(answer["url"], esc(link_label(answer["url"], site.repo)))}. '
        f"A summary in the words of this workspace, not {esc(site.provider)}'s own text.</p></section>"
    )


def panel(site, f, up):
    """What stands beside the status: the release that resolves it, a closing, a community patch, the next step."""
    p, rid = site.provider, f["id"]

    def text(value):
        return record_text(site, value, inline=True, up=up, link_ids=True, own=rid)

    rows_ = ""
    fixed, closed = f["fixed_in"], f["closed"]
    if fixed:
        detail = f'<p class="note">{text(fixed["detail"])}</p>' if fixed.get("detail") else ""
        rows_ += (
            f'<div><dt>Resolved in</dt><dd>{esc(site.release_name(fixed["release"]))}{detail}'
            f'<p class="note">Recorded {day(fixed["date"])}: {ext(fixed["url"], esc(link_label(fixed["url"], site.repo)))}</p></dd></div>'
        )
    if closed:
        when = f'{day(closed["date"])}: ' if closed.get("date") else ""
        rows_ += (
            f'<div><dt>{esc(site.label(closed["as"]))}</dt><dd>{text(closed["reason"])}'
            f'<p class="note">{when}{ext(closed["url"], esc(link_label(closed["url"], site.repo)))}</p></dd></div>'
        )
    for x in f["patches"]:
        who = f'Written by {esc(x["author"])}, ' + (
            f'authorised by {esc(x["authorised_by"])}.' if x["authorised_by"] else "not yet authorised."
        )
        rows_ += (
            f'<div><dt>Community patch</dt><dd>{ext(x["url"], "Patch " + esc(x["id"]))}: {text(x["description"])}'
            + (f'<p class="note">Applied in the <a href="{up}{site.patched_page}">patched release</a>, for those who need '
               f"the change now. {who} " if site.patched_page else f'<p class="note">{who} ')
            + f"A community patch is not {esc(p)}'s correction and does not change the status.</p></dd></div>"
        )
    if f["next"]:
        rows_ += (
            f'<div><dt>Next step</dt><dd>{text(f["next"]["action"])}'
            f'<p class="note">Taken by: {esc(f["next"]["role"])}</p></dd></div>'
        )
    return f'<dl class="panel">{rows_}</dl>' if rows_ else ""


def finding_page(site, f):
    """The page of one finding: header, tracker, discussion beside, then answer, facts and text."""
    up, p, rid = "../", site.provider, esc(f["id"])
    config = site.records_config

    def text(value, inline=False):
        return record_text(site, value, inline=inline, up=up, link_ids=True, own=f["id"])

    subjects = [d for d in f["datasets"] if d.get("role", "subject") == "subject"]
    concerns = [dataset_line(site, d, up) for d in subjects]
    if f["scope"].strip():
        concerns.append(text(f["scope"], inline=True))
    releases = ", ".join(
        f'<a href="{up}releases/{esc(r)}.html">{esc(site.release_name(r))}</a>' for r in f["releases"]
    )
    kind = community.KINDS[f["kind"]]
    facts = (
        f'<div><dt>Concerns</dt><dd>{"<br>".join(concerns)}</dd></div>'
        + (f"<div><dt>{esc(p)} release</dt><dd>{releases}</dd></div>" if releases else "")
        + f'<div><dt>Kind</dt><dd>{esc(kind["label"])}</dd></div>'
    )
    retained = "".join(
        f'<li><strong>{RETAINED[x["kind"]]}.</strong> {text(x["text"], inline=True)} '
        f'{ext(x["evidence_url"], esc(link_label(x["evidence_url"], site.repo)))}</li>'
        for x in f["retained"]
    )
    related = "".join(
        f'<li><a href="{esc(other)}.html">{esc(other)}</a> {esc(site.by_id[other]["title"])} '
        f'<span class="quiet">· {esc(site.label(site.by_id[other]["stage"]))}</span></li>'
        for other in f["related"]
    )
    source = f'{site.source_repo}/blob/{site.ref}/{f["path"]}'
    main = (
        answer_block(site, f, up)
        + panel(site, f, up)
        + "<h2>What was observed</h2>" + text(f["observation"])
        + (f"<h2>What it affects</h2>{text(f['exposure'])}" if f["exposure"].strip() else "")
        + (f"<h2>How it was checked</h2>{text(f['method'])}" if f["method"].strip() else "")
        + other_datasets(site, f, up)
        + (f'<h2>Related findings</h2><ul class="plain">{related}</ul>' if related else "")
        + (f"<h2>Also on record</h2><ul>{retained}</ul>" if retained else "")
        + (f"<h2>Details</h2>{text(f['notes'])}" if f["notes"].strip() else "")
        + f'<p class="source">Source of this page: {ext(source, "record " + rid + ".json on GitHub")} · '
        f'<a href="{up}api/v1/findings/{rid}.json">this finding as JSON</a></p>'
    )
    label = site.label(f["stage"])
    body = (
        '<div class="wrap page">'
        f'<header class="record-head"><nav class="crumb" aria-label="Breadcrumb"><a href="{up}findings.html">Findings</a> '
        f'<span aria-hidden="true">/</span> <a href="{up}findings.html#stage-{esc(f["stage"])}">{esc(label)}</a> '
        f'<span aria-hidden="true">/</span> <span aria-current="page">{rid}</span></nav>'
        f'<h1 dir="auto">{esc(f["title"])}</h1><dl class="facts">{facts}</dl></header>'
        + status.finding_tracker(site, f, up)
        + f'<div class="with-rail"><aside class="rail" aria-label="Discussion">{discussion_card(site, f, up)}</aside>'
        f'<div class="prose">{main}</div></div></div>'
    )
    names = community.release_names(f, config) if f["releases"] else ""
    description = f'{f["id"]}: {f["title"]}. Status: {label}.' + (f" {names}." if names else "")
    return site.shell(
        f'{f["id"]} · {f["title"]}', body, "findings.html", up=up, page=f'findings/{f["id"]}.html',
        description=description,
        head=f'<link rel="alternate" type="application/json" href="{up}api/v1/findings/{rid}.json">',
    )
