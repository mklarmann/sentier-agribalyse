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
        empty="No finding is waiting for a second measurement.",
    )


def ways(site, up=""):
    """The three ways to take part."""
    p = esc(site.provider)
    report = f"{site.repo}/issues/new?template={site.finding_form}"
    return (
        '<div class="ways">'
        f'<div class="card"><h3>Repeat a measurement</h3><p>Take a finding that needs a second measurement, repeat it on '
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
    opening = (
        f'<section class="wrap hero"><p class="eyebrow">{d} life-cycle inventory database</p>'
        f"<h1>Feedback on {p}'s inventory data, from the people who use it</h1>"
        f'<p class="lead">Users of the {d} life-cycle inventory database record here what they find in the data, check '
        f"each other's measurements and report the findings to {p}. The aim is a better database for everyone. "
        f"{p} decides what it changes.</p>"
        f'<div class="actions"><a class="button primary" href="findings.html">See the findings</a></div>'
        f"{shell.lookup(site)}</section>"
    )
    steps = (
        '<section class="wrap section" aria-labelledby="how"><div class="section-head"><h2 id="how">How it works</h2></div>'
        f"{status.path_with_counts(site)}</section>"
    )
    wanted = (
        '<section class="wrap section" aria-labelledby="help"><div class="section-head">'
        '<h2 id="help">Needs a second measurement</h2></div>'
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
