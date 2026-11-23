"""Public source register and review cases, joined by the finding IDs used by patches."""

import json
import re
from urllib.parse import urlsplit

import community
from . import findings, pages, quality
from .text import esc, ext, plural


def register(site):
    """Project records stay authoritative. An additional reviewed source may cite several cases."""
    sources = {}

    def add(key, kind, title, url, cases):
        if key in sources or any(case not in site.by_id for case in cases):
            raise ValueError(f"Duplicate source or unknown case in {key}")
        sources[key] = dict(id=key, kind=kind, title=title, url=url, cases=list(cases))

    for f in site.by_id.values():
        rid = f["id"]
        add(f"report-{rid}", "Finding", f["title"], f["reported"]["url"] or f"findings/{rid}.html", [rid])
        if f["answer"]:
            add(f"answer-{rid}", "Provider feedback", f'{site.provider} response to {rid}',
                f["answer"]["url"], [rid])
    for batch, item in pages.batches(site).items():
        add(f"feedback-{batch}", "Feedback report", f'Report to {site.provider} · {item["date"]}',
            f"feedback/{batch}.html", [f["id"] for f in item["findings"]])
    for c in site.contributions:
        add(c["id"], community.CONTRIBUTION_CLASS[c["class"]]["label"], c["title"],
            f'contributions/{c["id"]}.html', [])
    for r in site.records_config["releases"]:
        rid = r["id"]
        add(f"release-{rid}", "Database", r["name"], f"releases/{rid}.html",
            [f["id"] for f in site.by_id.values() if rid in f["releases"]])
    for code, item in site.datasets.items():
        add(f"inventory-{code}", "Inventory", f'{item["name"]} ({item["location"]})',
            f"datasets/{int(code)}.html", [f["id"] for f in item["findings"]])
    path = site.root / "community/sources.json"
    for s in json.loads(path.read_text()) if path.is_file() else []:
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", s["id"]) or urlsplit(s["url"]).scheme != "https":
            raise ValueError("A reviewed source needs an identifier and a public HTTPS address")
        add(s["id"], s["kind"], s["title"], s["url"], s["cases"])
    return sources


def sources(site):
    return site.derived("sources", lambda: register(site))


def case_sources(site, rid):
    return [s for s in sources(site).values() if rid in s["cases"]]


def patch_key(p):
    return f'{p["id"]}-{p["slug"]}'


def comparison_cases(site):
    return {f["id"]: {"title": f["title"], "patches": [patch_key(p) for p in f["patches"]]}
            for f in site.triage["findings"]}


def case_link(rid, up=""):
    return f'<a href="{up}cases/{esc(rid)}.html">{esc(rid)}</a>'


def table(noun, columns, filters, rows):
    controls = '<label class="field grow"><span>Search</span><input name="q" type="search" autocomplete="off"></label>'
    for key, (label, values) in filters.items():
        options = "".join(f'<option value="{esc(v)}">{esc(v)}</option>' for v in sorted(set(values)))
        controls += f'<label class="field"><span>{esc(label)}</span><select name="{key}"><option value="">All</option>{options}</select></label>'
    body = ""
    for facets, cells in rows:
        attrs = " ".join(f'data-{key}="{esc(value)}"' for key, value in facets.items())
        body += f'<tr {attrs}>' + "".join(
            f'<td data-label="{esc(label)}">{value}</td>' for label, value in zip(columns, cells, strict=True)
        ) + '</tr>'
    headings = "".join(f'<th scope="col">{esc(col)}</th>' for col in columns)
    return (f'<section data-register="{noun}"><form class="filter-row" role="search" hidden>{controls}'
            '<button type="reset" class="button">Clear filters</button></form>'
            f'<p role="status" aria-live="polite">{plural(len(rows), noun)}</p><div class="table-wrap"><table>'
            f'<thead><tr>{headings}</tr></thead><tbody>{body}</tbody></table></div></section>'
            '<script src="assets/register.js" defer></script>')


def source_list(site):
    rows = []
    for s in sources(site).values():
        links = ", ".join(case_link(rid) for rid in s["cases"]) or "No case linked"
        rows.append(({"kind": s["kind"], "search": s["id"]},
                     [f'<a href="{esc(s["url"])}">{esc(s["title"])}</a>', esc(s["kind"]), links]))
    return table("source", ["Source", "Kind", "Cases"], {"kind": ("Source kind", [s["kind"] for s in sources(site).values()])}, rows)


def case_list(site):
    rows = []
    for f in findings.recent(site):
        rid = f["id"]
        patch = "Registered patch" if f["patches"] else "No registered patch"
        stage = site.label(f["stage"])
        ids = ", ".join(p["id"] for p in f["patches"]) or "—"
        lookup = " ".join([f["scope"]] + [str(d["code"]) + " " + d["name"] + " " + d["location"] for d in f["datasets"]]
                          + [patch_key(p) for p in f["patches"]] + [s["id"] for s in case_sources(site, rid)])
        url, label, _ = findings.discussion(site, f)
        on_github = ext(url, esc(label)) if url else "—"
        rows.append(({"case": rid, "stage": stage, "patch": patch, "search": lookup},
                     [f'<a href="cases/{rid}.html">{rid} · {esc(f["title"])}</a>', esc(stage), esc(ids), on_github]))
    return table("case", ["Case", "Triage status", "Community patch", "Discussion"],
                 {"stage": ("Triage status", [r[0]["stage"] for r in rows]),
                  "patch": ("Patch", [r[0]["patch"] for r in rows])}, rows)


def build_register(site):
    count = plural(len(site.by_id), "case")
    return (f'<details class="build-cases"><summary>Filter {count} by dataset, triage status or patch</summary>'
            + case_list(site) + '<p><a href="cases.html">Open the full case register</a></p></details>')


def case_panel(site, f):
    rid = f["id"]
    items = []
    for s in case_sources(site, rid):
        href = s["url"] if "://" in s["url"] else "../" + s["url"]
        items.append(f'<li>{esc(s["kind"])} · <a href="{esc(href)}">{esc(s["title"])}</a></li>')
    patches = "".join(f'<li><a href="{esc(p["url"])}">{esc(patch_key(p))}</a> · '
                      + (f'authorised by {esc(p["authorised_by"])}' if p.get("authorised_by") else "authorisation pending")
                      + "</li>" for p in f["patches"])
    records = (site.last_run or {}).get("before_after") or {}
    cause_ids = {p["id"] for p in records.get("causes") or []}
    compared = site.compared.get("", {}).get("compared")
    result = ""
    if compared and any(patch_key(p) in cause_ids for p in f["patches"]):
        result = f'<p><a href="../{esc(compared)}?case={rid}#moved">Inspect this case in the build comparison</a></p>'
    return ('<section><h2 id="case-sources">Sources for this case</h2><ul>' + "".join(items) + '</ul>'
            '<h2>Patch record</h2>' + ('<ul>' + patches + '</ul>' if patches else '<p>No community patch is registered for this case.</p>')
            + f'<p><a href="../api/v1/cases/{rid}.json" download>Download the finding record used by the patch workflow</a></p>'
            + result + '</section>' + quality.case_summary(site, f))


def write(site):
    case_index = []
    for f in site.triage["findings"]:
        rid = f["id"]
        site.page(f"cases/{rid}.html", findings.finding_page(site, f, case_panel=case_panel(site, f)), f["changed"])
        site.write_json(f"api/v1/cases/{rid}.json", {k: f[k] for k in community.FINDING_FIELDS})
        case_index.append(dict(id=rid, title=f["title"], status=f["stage"], patches=[patch_key(p) for p in f["patches"]],
                               sources=[s["id"] for s in case_sources(site, rid)], record=f"cases/{rid}.json"))
    site.write_json("api/v1/cases.json", {"schema": "sentier-bafu/cases/1", "cases": case_index})
    site.write_json("api/v1/sources.json", {"schema": "sentier-bafu/sources/1", "sources": list(sources(site).values())})
