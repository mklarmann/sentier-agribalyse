"""The pages built from the records alone: feedback to the provider and its reports, one
page per provider release and per dataset, what changed (page and feed), housekeeping for
maintainers; and the generated blocks a prose page can ask for (patch table, data files)."""

from urllib.parse import quote
from xml.sax.saxutils import escape as xml

import community

from . import findings, shell
from .prose import record_text
from .text import day, day_text, esc, ext, link_label, plural, thousands

CAP = 50          # rows of one group on a page; the rest is one link to the filtered list
CHANGES = 200     # events on the changes page
FEED = 100        # events in the feed
ROLE_HEADINGS = (
    ("subject", "Findings about this dataset"),
    ("affected", "Findings that change a result of this dataset"),
    ("named", "Findings that name this dataset"),
)


def lower_first(text):
    return text[:1].lower() + text[1:]


def stage_of(site, key):
    return [f for f in site.triage["findings"] if f["stage"] == key]


# -------------------------------------------------------------------------- changes


def event_words(site, event):
    """One dated step of one finding, as a sentence around the finding's number: (before, after)."""
    p, f = site.provider, site.by_id[event["id"]]
    name = event["event"]
    if name == "reported":
        return "New finding ", ""
    if name == "repeated":
        return "A second person repeated the measurement of ", (
            "" if event["stage"] == "confirmed" else " and did not reproduce it")
    if name == "sent":
        return "", f" was reported to {p}"
    if name == "answer":
        return f"{p} answered ", f' ({community.OUTCOMES[f["answer"]["outcome"]]["label"].lower()})'
    if name == "fixed_in":
        return "", f' was resolved in {site.release_name(f["fixed_in"]["release"])}'
    return "", " was withdrawn" if event["stage"] == "withdrawn" else " was recorded for information"


def change_lines(site, events, up=""):
    """Dated steps, newest first: the date, what happened, and the finding's title."""
    lines = ""
    for event in events:
        before, after = event_words(site, event)
        rid = esc(event["id"])
        lines += (
            f'<li>{day(event["date"])}<span class="change-what">{esc(before)}<a href="{up}findings/{rid}.html">{rid}</a>{esc(after)}'
            f'<span class="quiet"> · {esc(site.by_id[event["id"]]["title"])}</span></span></li>'
        )
    return f'<ul class="changes">{lines}</ul>' if lines else '<p class="list-none">Nothing is recorded yet.</p>'


def changes_page(site):
    total = len(site.changes)
    more = f" This page shows the newest {CHANGES}." if total > CHANGES else ""
    body = (
        "<h1>What changed</h1>"
        f"<p>Every dated step the records hold, the newest first: a new finding, a second measurement, a report to "
        f"{esc(site.provider)}, its answer, a release that resolves a finding, a closing. {plural(total, 'step is', 'steps are')} recorded.{more} "
        'The same list is available as a <a href="feed.xml">feed</a>.</p>'
        + change_lines(site, site.changes[:CHANGES])
    )
    return shell.generated_page(
        site, "What changed", body, "changes.html", current="findings.html",
        description=f"Every dated step recorded for a finding on {site.provider}'s inventory data, the newest first.",
    )


def feed(site):
    """The newest changes as an Atom feed. Nothing in it depends on the time of the build."""
    base = site.config["site_url"]
    newest = site.changes[0]["date"] if site.changes else site.built
    entries = ""
    for event in site.changes[:FEED]:
        before, after = event_words(site, event)
        f = site.by_id[event["id"]]
        address = f'{base}findings/{event["id"]}.html'
        entries += (
            f'<entry><id>{xml(address)}#{xml(event["event"])}-{xml(event["date"])}</id>'
            f'<title>{xml(before + event["id"] + after)}</title><updated>{xml(event["date"])}T00:00:00Z</updated>'
            f'<link href="{xml(address)}"/><summary>{xml(f["title"])}</summary></entry>\n'
        )
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom">'
        f'<id>{xml(base)}feed.xml</id><title>{xml(site.dataset)} findings: what changed</title>'
        f'<updated>{xml(newest)}T00:00:00Z</updated><author><name>{xml(site.repo.rstrip("/").rsplit("/", 1)[-1])}</name></author>'
        f'<link rel="self" href="{xml(base)}feed.xml"/><link href="{xml(base)}changes.html"/>\n{entries}</feed>\n'
    )


# ------------------------------------------------------------------------- feedback


def batches(site):
    """The reports to the provider: {batch id: {date, url, findings}}, the newest first."""
    found = {}
    for f in site.triage["findings"]:
        sent = f["sent"]
        if sent:
            entry = found.setdefault(sent["batch"], {"date": sent["date"], "url": sent["url"], "findings": []})
            entry["findings"].append(f)
    return dict(sorted(found.items(), key=lambda item: (item[1]["date"], item[0]), reverse=True))


def answer_line(site, up):
    def line(f):
        answer = f["answer"]
        if not answer:
            return ""
        return (f'<p class="row-answer"><strong>{esc(site.provider)}\'s answer, {day(answer["date"])}:</strong> '
                f'{record_text(site, answer["summary"], inline=True, up=up, link_ids=True, own=f["id"])}</p>')
    return line


def feedback_lists(site, up=""):
    """What the provider received and answered and what is resolved: four numbers, then the findings behind each,
    then the reports by date. Everything comes from the dated evidence of the records."""
    p = esc(site.provider)
    sent = sorted(stage_of(site, "sent"), key=lambda f: (f["sent"]["date"], community.finding_number(f)))
    answered = sorted(stage_of(site, "answered"), key=lambda f: (f["answer"]["date"] or "", community.finding_number(f)), reverse=True)
    fixed = sorted(stage_of(site, "fixed"), key=lambda f: (f["fixed_in"]["date"] or "", community.finding_number(f)), reverse=True)
    ready = sorted(stage_of(site, "confirmed"), key=lambda f: (f["repeated"]["date"] or "", community.finding_number(f)))
    undated = sum(1 for f in answered + fixed if not f["sent"])
    groups = (
        ("awaiting", "Reported, no answer yet", sent, "sent", None,
         f"No finding is recorded as reported to {p} and still without an answer."),
        ("answered", f"Answered by {p}", answered, "answered", answer_line(site, up), f"No answer from {p} is recorded yet."),
        ("resolved", "Resolved", fixed, "fixed", None, "No finding is recorded as resolved yet."),
        ("ready", "Repeated, not yet reported", ready, "confirmed", None,
         "No finding is waiting to be reported."),
    )
    tally = '<ul class="tally">' + "".join(
        f'<li><a href="#{anchor}"><strong>{thousands(len(found))}</strong> <span>{lower_first(title)}</span></a></li>'
        for anchor, title, found, _, _, _ in groups
    ) + "</ul>"
    out = tally
    for anchor, title, found, key, extra, empty in groups:
        out += f'<h2 id="{anchor}">{title}</h2>'
        if anchor == "answered" and undated:
            out += (f"<p>For {thousands(undated)} of the findings that {p} has answered or that are resolved, "
                    "the date they were reported is not recorded.</p>")
        out += findings.rows(site, found, up, limit=CAP, more=f"{up}findings.html#stage-{key}", empty=empty, extra=extra)
    reports = batches(site)
    out += '<h2 id="reports">Reports by date</h2>'
    if reports:
        out += '<ul class="plain">' + "".join(
            f'<li><a href="{up}feedback/{esc(batch)}.html">Report of {day(entry["date"], long=True)}</a> '
            f'<span class="quiet">· {plural(len(entry["findings"]), "finding")}, '
            f'{sum(1 for f in entry["findings"] if f["answer"])} answered</span></li>'
            for batch, entry in reports.items()
        ) + "</ul>"
    else:
        out += f'<p class="list-none">No report to {p} is recorded with its date yet.</p>'
    return out


def batch_page(site, batch, entry):
    """One report to the provider: the findings that went together, and what came back."""
    up, p = "../", esc(site.provider)
    found = sorted(entry["findings"], key=community.finding_number)
    waiting = [f for f in found if f["stage"] == "sent"]
    answered = [f for f in found if f["answer"] and f["stage"] != "sent"]
    rest = [f for f in found if f not in waiting and f not in answered]
    when = day(entry["date"], long=True)
    body = (
        f'<nav class="crumb" aria-label="Breadcrumb"><a href="{up}feedback.html">Feedback to {p}</a> '
        f'<span aria-hidden="true">/</span> <span aria-current="page">{esc(batch)}</span></nav>'
        f"<h1>Report to {p} of {when}</h1>"
        f"<p>{plural(len(found), 'finding was', 'findings were')} reported to {p} together on {when}. "
        f"{p} decides what it changes. Where the report is recorded: {ext(entry['url'], esc(link_label(entry['url'], site.repo)))}.</p>"
        + (f'<h2 id="awaiting">No answer yet</h2>{findings.rows(site, waiting, up)}' if waiting else "")
        + (f'<h2 id="answered">Answered by {p}</h2>{findings.rows(site, answered, up, extra=answer_line(site, up))}' if answered else "")
        + (f'<h2 id="other">Resolved or closed without a recorded answer</h2>{findings.rows(site, rest, up)}' if rest else "")
    )
    return shell.generated_page(
        site, f"Report to {site.provider} of {day_text(entry['date'])}", body, f"feedback/{batch}.html",
        current="feedback.html", up=up,
        description=f"{plural(len(found), 'finding')} reported to {site.provider} on {day_text(entry['date'])}, with {site.provider}'s answers.",
    )


# ------------------------------------------------------------------------- releases


def release_page(site, rid, entry):
    """What is known about one provider release, by status."""
    up, p, name = "../", esc(site.provider), esc(entry["name"])
    observed = [site.by_id[i] for i in entry["findings"]]
    here = [site.by_id[i] for i in entry["corrected"]]
    groups = []
    for key in ("answered", "sent", "confirmed", "filed"):
        groups.append((key, site.label(key), [f for f in observed if f["stage"] == key]))
    groups.append(("fixed", "Resolved in this release", here))
    groups.append(("fixed-later", "Resolved in another release",
                   [f for f in observed if f["stage"] == "fixed" and f not in here]))
    for key in ("not-a-defect", "withdrawn"):
        groups.append((key, site.label(key), [f for f in observed if f["stage"] == key]))
    groups = [g for g in groups if g[2]]
    summary = '<ul class="tally">' + "".join(
        f'<li><a href="#status-{key}"><strong>{thousands(len(found))}</strong> <span>{esc(lower_first(title))}</span></a></li>'
        for key, title, found in groups
    ) + "</ul>"
    sections = ""
    for key, title, found in groups:
        newest = sorted(found, key=lambda f: (f["changed"] or "", community.finding_number(f)), reverse=True)
        stage = "fixed" if key.startswith("fixed") else key
        sections += f'<h2 id="status-{key}">{esc(title)}</h2>' + findings.rows(
            site, newest, up, limit=CAP, more=f"{up}findings.html?release={quote(rid)}#stage-{stage}")
    body = (
        f'<nav class="crumb" aria-label="Breadcrumb"><a href="{up}findings.html">Findings</a> '
        f'<span aria-hidden="true">/</span> <span aria-current="page">{name}</span></nav>'
        f"<h1>Known in {name}</h1>"
        f"<p>{plural(len(observed), 'finding was', 'findings were')} observed in {name}"
        + (f"; {thousands(len(here))} of the findings {'is' if len(here) == 1 else 'are'} resolved in it" if here else "")
        + f". Only what someone has reported is listed here. {p} decides what it changes"
        + (f'; a community patch in the <a href="{up}{site.patched_page}">patched release</a> is not {p}\'s correction'
           if site.patched_page else "")
        + ".</p>"
        + (f"<p>{name} is built on {esc(entry['background'])}.</p>" if entry.get("background") else "")
        + (summary + sections if groups else '<p class="list-none">No finding names this release.</p>')
    )
    return shell.generated_page(
        site, f"Known in {entry['name']}", body, f"releases/{rid}.html", current="findings.html", up=up,
        description=f"The findings observed in {entry['name']}, by status, and the findings resolved in it.",
    )


# ------------------------------------------------------------------------- datasets


def dataset_page(site, code, entry):
    """What the findings say about one dataset. A code is listed as soon as a finding names it."""
    up, p = "../", esc(site.provider)
    title = f'{code} {entry["name"]} ({entry["location"]})'
    sections = ""
    for role, heading in ROLE_HEADINGS:
        found = [site.by_id[x["id"]] for x in entry["findings"] if x["role"] == role and x["id"] in site.by_id]
        if found:
            sections += f"<h2>{heading}</h2>" + findings.rows(site, found, up)
    by_id = {x["id"]: x for x in (site.patches or {}).get("patches", [])}
    patches = "".join(
        f'<li>{ext(by_id[pid]["url"], "Patch " + esc(pid))}: '
        f'{record_text(site, by_id[pid]["description"], inline=True)}</li>'
        for pid in entry["patches"] if pid in by_id
    )
    if patches:
        sections += (f'<h2>Community patches</h2><ul class="plain">{patches}</ul>'
                     + (f'<p>They are applied in the <a href="{up}{site.patched_page}">patched release</a>. '
                        if site.patched_page else "<p>")
                     + f"A patch is not {p}'s correction.</p>")
    report = f"{site.repo}/issues/new?template={site.finding_form}&dataset={quote(title)}"
    body = (
        f'<nav class="crumb" aria-label="Breadcrumb"><a href="{up}findings.html">Findings</a> '
        f'<span aria-hidden="true">/</span> <span aria-current="page">Dataset {code}</span></nav>'
        f'<p class="eyebrow">Dataset {code}</p><h1 dir="auto">{esc(entry["name"])} ({esc(entry["location"])})</h1>'
        f"<p>What the findings say about dataset {code} of the {esc(site.dataset)} database. "
        "Only what someone has reported is listed: a dataset without a finding is not thereby free of errors.</p>"
        + sections
        + f'<p class="actions">{ext(report, "Report something about this dataset", "button ext")}'
        f'<a class="arrow" href="{up}findings.html">All findings</a></p>'
    )
    return shell.generated_page(
        site, f"Dataset {title}", body, f"datasets/{code}.html", current="findings.html", up=up,
        description=f'Findings on dataset {title} of the {site.dataset} database.',
        head=f'<link rel="alternate" type="application/json" href="{up}api/v1/datasets.json">',
    )


# --------------------------------------------------------------------- housekeeping


def housekeeping(site):
    """For maintainers: what in the records, the issues and the patches needs a hand."""
    p, t = esc(site.provider), site.triage

    def ids(found):
        return ", ".join(f'<a href="findings/{esc(f["id"])}.html">{esc(f["id"])}</a>' for f in found)

    def section(anchor, title, text, items):
        return f'<h2 id="{anchor}">{title}</h2><p>{text}</p>' + (items or '<p class="list-none">Nothing to do.</p>')

    unlisted = '<ul class="plain">' + "".join(
        f'<li>{ext(i["url"], "Issue #" + str(int(i["number"])))} <span class="quiet">· last activity {day(i["updated"])}</span></li>'
        for i in t["unlisted"]
    ) + "</ul>" if t["unlisted"] else ""
    without = [site.by_id[i] for i in t["without_issue"]]
    no_issue = '<ul class="plain">' + "".join(
        f'<li><a href="findings/{esc(f["id"])}.html">{esc(f["id"])}</a> {esc(f["title"])}'
        + "".join(f" · {ext(u, esc(link_label(u, site.repo)))}" for u in f["threads"][:1]) + "</li>"
        for f in without
    ) + "</ul>" if without else ""
    differences = t["label_differences"]
    labels = "<p>" + ", ".join(
        ext(f'{site.repo}/issues/{int(d["issue"])}', f'#{int(d["issue"])}') for d in differences
    ) + "</p>" if differences else ""
    longest = ""
    for key in community.OPEN_STAGES:
        waiting = sorted(stage_of(site, key), key=lambda f: (f["waiting_since"] or "9999", community.finding_number(f)))[:10]
        if waiting:
            longest += f'<h3>{esc(site.label(key))}</h3><ul class="changes">' + "".join(
                f'<li>{day(f["waiting_since"]) or "<span>no date</span>"}<span class="change-what"><a href="findings/{esc(f["id"])}.html">{esc(f["id"])}</a>'
                f'<span class="quiet"> · {esc(f["title"])}</span></span></li>'
                for f in waiting
            ) + "</ul>"
    to_check = [f for f in stage_of(site, "answered") if f["answer"]["outcome"] != "declined"]
    loose = community.patches_without_finding(site.patches)
    patches = '<ul class="plain">' + "".join(
        f'<li>{ext(x["url"], "Patch " + esc(x["id"]))}: {record_text(site, x["description"], inline=True)}</li>' for x in loose
    ) + "</ul>" if loose else ""
    source = {None: "Issues were not read for this build, so the first and third list are empty.",
              "live": "Issues were read from GitHub when the site was built."}.get(
        site.issues_source, "Issues were read from a snapshot.")
    body = (
        "<h1>Housekeeping</h1>"
        "<p>For maintainers: what in the records, the issues and the community patches needs a hand. "
        f"Everything here is computed when the site is built. {source}</p>"
        + section("reports", "Reports without a record",
                  "An issue filed as a finding gets its number when its record is written.", unlisted)
        + section("no-issue", "Records without an issue in this repository",
                  "These findings are discussed elsewhere only.", no_issue)
        + section("labels", "Issue labels that differ from the record",
                  "Labels follow the records. The build log names the labels to add and to remove for each issue.", labels)
        + section("waiting", "Longest waiting", "The ten findings of each open status that have waited longest for their next step.", longest)
        + section("check", "Answered, not yet resolved",
                  f"{p} has answered these findings, and none of them is recorded as resolved.",
                  f"<p>{ids(sorted(to_check, key=community.finding_number))}</p>" if to_check else "")
        + section("patches", "Community patches that name no finding",
                  "A patch should name the finding it answers, so that its page can show the patch.", patches)
    )
    return shell.generated_page(
        site, "Housekeeping", body, "housekeeping.html",
        description="For maintainers: what in the records, the issues and the community patches needs a hand.",
    )


# ------------------------------------------------------------------ generated blocks


def patch_table(site, up=""):
    """Every community patch of the registry snapshot: what it does, the finding it answers,
    who wrote it and who authorised it, as the registry names them."""
    listed = (site.patches or {}).get("patches", [])
    if not listed:
        return '<p class="list-none">No community patch is registered.</p>'
    head = ("Patch", "What it does", "Finding", "Written by", "Authorised by")
    lines = ""
    for x in listed:
        answers = ", ".join(f'<a href="{up}findings/{esc(i)}.html">{esc(i)}</a>' for i in x["findings"] if i in site.by_id)
        cells = (
            ext(x["url"], esc(x["id"])),
            record_text(site, x["description"], inline=True),
            answers or '<span class="quiet">none named</span>',
            esc(x["author"]),
            esc(x["authorised_by"]) if x["authorised_by"] else '<span class="quiet">not yet</span>',
        )
        lines += '<tr role="row">' + "".join(
            f'<td role="cell" data-label="{label}">{cell}</td>' for label, cell in zip(head, cells)
        ) + "</tr>"
    return (
        '<div class="table-wrap"><table role="table" class="cols-5 key-short"><thead role="rowgroup"><tr role="row">'
        + "".join(f'<th role="columnheader" scope="col">{label}</th>' for label in head)
        + f'</tr></thead><tbody role="rowgroup">{lines}</tbody></table></div>'
    )


DATA_FILES = (
    ("api/v1/findings.json", "The status vocabulary and one entry per finding: number, title, kind, status, dataset codes, releases, patches, the date of each step."),
    ("api/v1/findings/F1.json", "One file per finding: the full record and what is derived from it. Replace F1 by any finding's number."),
    ("api/v1/datasets.json", "For every dataset code a finding names: its name and location, the findings with their role, the patches."),
    ("api/v1/contributions.json", "The classes and one entry per contribution."),
    ("api/v1/status.json", "The number of findings by status and the identity of the build."),
    ("api/v1/last-run.json", "The last release build: GitHub's record of the run, the manifest it kept and every line it printed."),
    ("schema/finding.schema.json", "The JSON Schema of a finding record."),
    ("schema/contribution.schema.json", "The JSON Schema of a contribution record."),
    ("ledger.md", "The findings as one table, one line each, in Markdown."),
    ("feed.xml", "What changed, as an Atom feed."),
    ("sitemap.xml", "Every page of the site."),
)


def data_files(site, up=""):
    """The machine-readable files of the site, each with a link and what it holds."""
    lines = "".join(
        f'<tr role="row"><td role="cell" data-label="File"><a href="{up}{esc(path)}"><code>{esc(path)}</code></a></td>'
        f'<td role="cell" data-label="What it holds">{esc(text)}</td></tr>'
        for path, text in DATA_FILES
        # the record of the last release build is a file of a site that shows one
        if path != "api/v1/last-run.json" or site.last_run is not None
    )
    return (
        '<div class="table-wrap"><table role="table" class="cols-2"><thead role="rowgroup"><tr role="row">'
        '<th role="columnheader" scope="col">File</th><th role="columnheader" scope="col">What it holds</th>'
        f'</tr></thead><tbody role="rowgroup">{lines}</tbody></table></div>'
    )


def sitemap(site):
    base = site.config["site_url"]
    urls = "".join(
        f"<url><loc>{xml(base + page)}</loc>" + (f"<lastmod>{xml(changed)}</lastmod>" if changed else "") + "</url>\n"
        for page, changed in sorted(site.pages.items())
    )
    return f'<?xml version="1.0" encoding="utf-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n'
