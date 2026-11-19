"""The overview: what happens here and why, the five steps with their counts, what needs a
second measurement now, what changed recently, the ways to take part, the patched copy.
Each thing is said once."""

from . import findings, pages, shell, status
from .text import esc, ext


def second_measurement_list(site, up="", limit=5):
    """The findings that need a second measurement, the longest waiting first."""
    waiting = sorted(
        (f for f in site.triage["findings"] if f["stage"] == "filed"),
        key=lambda f: (f["waiting_since"] or "9999", f["id"]),
    )
    return findings.rows(
        site, waiting, up, limit=limit, more=f"{up}findings.html?sort=waiting#stage-filed",
        empty="No finding is awaiting verification.",
    )


def ways(site, up=""):
    """The three ways to take part."""
    p = esc(site.provider)
    report = site.finding_submission()
    return (
        '<div class="ways">'
        f'<div class="card"><h3>Verify a finding</h3><p>Choose an open finding, check it on '
        f"{p}'s files and write in its discussion what you got. A different result is as useful as the same one.</p>"
        f'<a class="arrow" href="{up}take-part.html">How to take part</a></div>'
        '<div class="card"><h3>Report a finding</h3><p>Say which dataset and which release, what you measured and how. '
        f'Reporting needs a free GitHub account.</p>{ext(report, "Report a finding")}</div>'
        '<div class="card"><h3>Propose a contribution</h3><p>A mapping, a model, a rebuilt inventory or a method variant, '
        "with its evidence and the checks it must pass.</p>"
        f'<a class="arrow" href="{up}contributions.html">Contributions</a></div></div>'
    )


def overview(site):
    p, d = esc(site.provider), esc(site.dataset)
    waiting = site.triage["counts"].get("filed", 0)
    latest = site.compared.get("", {})
    comparison = latest.get("compared") or latest.get("review")
    section = "#moved" if (site.last_run or {}).get("before_after") else ""
    compare_link = (
        f' <a class="button" href="{esc(comparison)}{section}">Compare results before and after</a>'
        if comparison else ""
    )
    browse = ('<a class="button primary" href="cases.html">Browse cases</a> <a class="button" href="sources.html">Explore sources</a>'
              if site.config.get("case_review") else '<a class="button primary" href="findings.html">See the findings</a>')
    intro = site.config.get("home_intro", {})
    if intro.get("feedback_actions") and site.config.get("case_review"):
        browse = (f'<a class="button primary" href="{esc(site.finding_submission())}">Report a finding</a> '
                  '<a class="button" href="cases.html">Browse cases</a>')
        compare_link = ""
    heading = esc(intro.get("heading", f"Feedback on {site.provider}'s inventory data, from the people who use it"))
    lead = esc(intro.get("lead",
        f"Users of the {site.dataset} life-cycle inventory database record here what they find in the data, "
        f"check each other's measurements and report the findings to {site.provider}. "
        f"The aim is a better database for everyone. {site.provider} decides what it changes."))
    opening = (
        f'<section class="wrap hero"><p class="eyebrow">{d} life-cycle inventory database</p>'
        f'<h1>{heading}</h1><p class="lead">{lead}</p>'
        f'<div class="actions">{browse}{compare_link}</div>'
        f"{shell.lookup(site)}</section>"
    )
    navigation = dict(site.config.get("nav", []))
    workflow = "".join(
        f'<li><a href="{esc(page)}">{esc(navigation[page])}</a><span>{esc(action)}</span></li>'
        for page, action in site.config.get("review_workflow", [])
    )
    journey = f'<ol class="review-workflow" aria-label="Explore the review process">{workflow}</ol>' if workflow else ""
    steps = (
        '<section class="wrap section" aria-labelledby="how"><div class="section-head"><h2 id="how">How it works</h2></div>'
        f"{journey}{status.path_with_counts(site)}</section>"
    )
    wanted = (
        '<section class="wrap section" aria-labelledby="help"><div class="section-head">'
        '<h2 id="help">Findings awaiting verification</h2></div>'
        + second_measurement_list(site) + "</section>"
    ) if waiting else ""
    recent = (
        '<section class="wrap section" aria-labelledby="recent"><div class="section-head"><h2 id="recent">Recently</h2></div>'
        + pages.change_lines(site, site.changes[:5])
        + '<div class="actions"><a class="arrow" href="changes.html">All changes</a></div></section>'
    ) if site.changes else ""
    part = (
        '<section class="wrap section" aria-labelledby="part"><div class="section-head"><h2 id="part">Take part</h2></div>'
        + ways(site)
        + (f'<p class="aside">For those who need a change now, the <a href="{site.patched_page}">patched copy</a> '
           f"applies community patches to a copy of {p}'s files. A community patch is not {p}'s correction.</p>"
           if site.patched_page else "")
        + "</section>"
    )
    return shell.shell(site, "Overview", opening + steps + wanted + recent + part, "index.html", page="index.html")
