"""The page of a review: choose causes, and see the pair of builds that differs by exactly them.

It shows one file, `review.json` (`scripts/runrecord/review.py`): the builds, what each
contains, what each cause claims, and the pairs that were compared. Each pair leads to the
page of its comparison (`beforeafter.py`). The page knows no dataset and no tool.

`body` is the page without a frame, as in `beforeafter.py`. Without the script it lists
every pair with what it differs by and its counts per class; the script
(`assets/review.js`) lets a reader tick causes and finds the pair that isolates them, or says
which build is missing.
"""

import json

from runrecord import before_after, review

from .beforeafter import KINDS, STYLE, as_data, capital, claim_line, plain
from .text import esc, plural, thousands

SCRIPT = "assets/review.js"


def counts(classes):
    """The values of one pair per class, the classes that hold none left out."""
    if not classes:
        return '<span class="quiet">not counted</span>'
    return '<span class="rv-counts">' + " ".join(
        f'<span><span class="ba-key k-{KINDS[kind]}"></span><b>{thousands(classes[kind])}</b> {esc(kind)}</span>'
        for kind in before_after.CLASSES if classes.get(kind)
    ) + "</span>"


def body(data, back=None, said=plain, file=None, up="", embedded=False):
    """The page of one review, without a frame; the arguments are those of `beforeafter.body`."""
    runs = {run["id"]: run for run in data["runs"]}
    causes = {cause["id"]: cause for cause in data["causes"]}
    words = {"one": "item", "many": "items"}

    def named(ids):
        return ", ".join(f"<code>{esc(i)}</code>" for i in ids) or "nothing"

    choose = "".join(
        f'<label class="rv-cause"><input type="checkbox" data-rv-cause value="{esc(cause["id"])}" disabled><span class="rv-about">'
        + (f'<span class="tag">{esc(cause["kind"])}</span> ' if cause.get("kind") else "")
        + (f'<strong>{said(cause["title"])}</strong> ' if cause.get("title") else "")
        + (f'<a href="{esc(cause["link"])}"><code>{esc(cause["id"])}</code></a>' if cause.get("link") else f'<code>{esc(cause["id"])}</code>')
        + (claim_line(cause.get("claim"), words, said) or '<span class="ba-claim">It states no claim.</span>')
        + "</span></label>"
        for cause in data["causes"]
    )
    rows = ""
    for pair in data["pairs"]:
        added, removed = review.difference(data, pair)
        page = pair.get("page")
        link = f'<a href="{esc(page)}">Compare</a>' if page else '<span class="quiet">no page</span>'
        differs = named(sorted(added)) + (f"; without {named(sorted(removed))}" if removed else "")
        rows += (
            f'<tr><th scope="row">{esc(runs[pair["before"]]["label"])}</th><td>{esc(runs[pair["after"]]["label"])}</td>'
            f"<td>{differs}</td><td>{counts(pair.get('classes'))}</td><td>{link}</td></tr>"
        )
    pairs = (
        '<div class="table-wrap"><table class="ba-table"><thead><tr><th scope="col">Before</th><th scope="col">After</th>'
        '<th scope="col">Differs by</th><th scope="col">Values per class</th><th scope="col">Comparison</th></tr></thead>'
        f"<tbody>{rows}</tbody></table></div>"
        if rows else '<p class="list-none">No two builds were compared.</p>'
    )
    builds = ""
    for run in data["runs"]:
        twin = runs.get(run.get("replica_of") or "")
        repeat = {True: "Two builds of this state agree.", False: "Two builds of this state differ.", None: ""}[run.get("reproducible")]
        facts = "".join(f"<dt>{esc(key)}</dt><dd>{esc(value)}</dd>" for key, value in run.get("identity", {}).items())
        builds += (
            f'<div class="card"><p class="ba-side">{esc(run["label"])}</p>'
            f'<p class="card-meta">Contains {named(run.get("contains", []))}.'
            + (f" A second build of {esc(twin['label'])}." if twin else "")
            + (f" {repeat}" if repeat else "")
            + "</p>"
            + (f'<dl class="rv-id">{facts}</dl>' if facts else "")
            + "</div>"
        )
    payload = json.dumps(
        {"runs": data["runs"], "pairs": data["pairs"], "kinds": KINDS,
         "causes": [{"id": c["id"], "title": c.get("title")} for c in data["causes"]]},
        ensure_ascii=False, separators=(",", ":"), allow_nan=False,
    )
    payload = as_data(payload)
    crumb = f'<p class="crumb"><a href="{esc(back[0])}">{esc(back[1])}</a></p>' if back else ""
    notes = "".join(f"<li>{said(note)}</li>" for note in data.get("notes") or ())
    as_file = f'<p class="note">The same index as a file: <a href="{esc(file)}"><code>{esc(file)}</code></a>.</p>' if file else ""
    title = f'<h2 id="review">{esc(data["title"])}</h2>' if embedded else f'<p class="eyebrow">Review</p><h1>{esc(data["title"])}</h1>'
    h = "h3" if embedded else "h2"
    notes_id = "review-notes" if embedded else "notes"
    return (
        f'{crumb}{title}'
        f'<p class="lead">A change is judged by two builds that differ by exactly it. '
        f'{capital(plural(len(data["runs"]), "build"))} and {plural(len(data["pairs"]), "comparison")} are here.</p>'
        '<div data-review>'
        f'<{h} id="choose">Choose what to review</{h}>'
        '<p>Tick one cause or several. The page looks for two builds that differ by exactly your choice.</p>'
        f'<div class="rv-causes">{choose}</div>'
        '<div class="rv-found" data-rv-found hidden role="status" aria-live="polite"></div>'
        f'<script type="application/json" data-rv-data>{payload}</script></div>'
        f'<{h} id="pairs">The comparisons</{h}>{pairs}'
        f'<{h} id="builds">The builds</{h}><div class="ba-sides">{builds}</div>'
        + (f'<{h} id="{notes_id}">Notes</{h}><ul class="plain">{notes}</ul>' if notes else "")
        + as_file
        + f'<script src="{up}{SCRIPT}" defer></script>'
    )


def page(site, data, name, back=None, current=None, file=None):
    """The whole page of one review, in the frame of a site the shared build writes."""
    from . import shell
    from .lastrun import inline

    inner = body(data, back, lambda text: inline(site, text, ""), file or f'api/v1/{name.removesuffix(".html")}.json')
    framed = f'<div class="wrap page ba-page"><article class="prose wide">{inner}</article></div>'
    return shell.shell(site, data["title"], framed, current or name, page=name,
                       description=f'{data["title"]}: the builds, what each contains, and the pairs that were compared.',
                       head=f'<link rel="stylesheet" href="{STYLE}">')
