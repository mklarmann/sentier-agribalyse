"""Case selection and the recorded scope of the current build comparison."""

from . import findings
from .cases import patch_key
from .text import esc, plural, thousands


def whole_result(data, diagnostics, config):
    if data:
        items = data["items"]
        indicator = data.get("indicator") or {"one": "indicator", "many": "indicators"}
        return (f'<p><strong>Whole build</strong> · {esc(plural(items["compared"], items["one"], items["many"]))} compared '
                f'across {esc(plural(len(data["indicators"]), indicator["one"], indicator["many"]))}. '
                f'{thousands(items["moved"])} changed.</p>')
    items = diagnostics["item"]
    total = diagnostics["items_count"]["all"]
    summary = (f'<p><strong>Whole build</strong> · {esc(plural(total, items["one"], items["many"]))}, '
               f'{plural(len(diagnostics["indicators"]), "indicator")} and {plural(len(diagnostics["steps"]), "build step")}.</p>')
    key = config.get("headline_indicator")
    result = diagnostics["counts"]["total"].get(key, {})
    if result.get("classes"):
        name = next(i["name"] for i in diagnostics["indicators"] if i["id"] == key)
        counts = " · ".join(f"{esc(label.capitalize())} {thousands(n)}" for label, n in result["classes"].items() if n)
        summary += f'<p>{esc(name)} · {counts}</p>'
    return summary


def case_result(site, case, data):
    rid = esc(case["id"])
    registered = {patch_key(p) for p in case["patches"]}
    causes = [c for c in (data or {}).get("causes", []) if c["id"] in registered]
    parts = [f'<p><strong>{rid}</strong> · {esc(site.label(case["stage"]))}</p>']
    for cause in causes:
        rows = (data.get("rows") or {"one": "row", "many": "rows"})
        changes = []
        if cause.get("rows") is not None:
            changes.append(f'{esc(plural(cause["rows"], rows["one"], rows["many"]))} changed')
        if cause.get("moved") is not None:
            items = data["items"]
            changes.append(f'{esc(plural(cause["moved"], items["one"], items["many"]))} with changed impact results')
        parts.append(f'<p>{esc(cause["title"])} {" · ".join(changes)}</p>')
    if not causes:
        parts.append('<p>This build records no separate impact measurement for this case.</p>')
    record = f'cases/{rid}.html'
    evidence = (case.get("closed") or {}).get("reason") or case.get("observation")
    if evidence and not causes:
        from .lastrun import inline
        parts.append(f'<p>{inline(site, evidence, "")}</p>')
    parts.append(f'<p><a href="{record}">Open case {rid}</a> · <a href="{record}#case-sources">Sources for {rid}</a></p>')
    return "".join(parts)


def opening(site, data, diagnostics, back, config, said):
    cases = findings.recent(site)
    options = "".join(f'<option value="{esc(f["id"])}">{esc(f["id"])} · {esc(f["title"])}</option>' for f in cases)
    sides = (data["before"], data["after"]) if data else (diagnostics["states"][0], diagnostics["states"][-1])
    pair = "".join(
        f'<div class="comparison-state"><p class="comparison-state-label">{label}</p>'
        f'<strong class="comparison-state-name">{esc(side["label"])}</strong>'
        + (f'<p class="comparison-state-detail">{said(side["about"])}</p>' if side.get("about") else "") + '</div>'
        for label, side in zip(("Before", "After"), sides, strict=True)
    )
    build = site.walk_page or site.patched_page or "index.html"
    run = config.get("run_url") or (back[0] if back else build)
    sources = config.get("sources_url", "sources.html")
    whole = (whole_result(data, diagnostics, config)
             + f'<p><a href="{esc(run)}">Build record</a> · <a href="{esc(sources)}">Sources</a></p>')
    templates = "".join(f'<template data-result-case="{esc(f["id"])}">{case_result(site, f, data)}</template>' for f in cases)
    intro = config.get("intro") or (data or diagnostics)["title"]
    return (f'<div class="comparison-opening"><p class="comparison-crumb"><a href="{esc(build)}">Build</a></p>'
            f'<h1 class="comparison-title">Comparison</h1><p class="comparison-intro">{esc(intro)}</p>'
            '<div class="comparison-filter" data-review-filter hidden><label for="review-case">Review case</label>'
            f'<select id="review-case" name="case"><option value="">All cases</option>{options}</select></div>'
            '<noscript><p><a href="cases.html">Browse the case register</a></p></noscript>'
            f'<div class="comparison-pair">{pair}</div><h2 class="comparison-results-title">Results</h2>'
            f'<div data-review-result aria-live="polite">{whole}</div>'
            f'<template data-result-case="">{whole}</template>{templates}</div>')
