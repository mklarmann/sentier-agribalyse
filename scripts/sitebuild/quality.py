"""Build views of the quality measurements of the identified inventory."""

from pathlib import Path
import subprocess
import tempfile

from .text import esc

CHECKS = {
    "reference": ("Reference product", "One reference output agrees with the declared product, unit and amount."),
    "suppliers": ("Supplier links", "Each technosphere exchange resolves to a unique supplier number in the same unit."),
    "exchanges": ("Inventory content", "The dataset has at least one exchange besides its reference output."),
    "uncertainty": ("Uncertainty coverage", "Each non-production exchange declares a distribution with a nonzero spread."),
    "signs": ("Exchange signs", "Negative amounts are flagged for review. Some represent credits or avoided burdens."),
}


def measure(site, archive, download):
    record = site.last_run or {}
    files = (record.get("summary") or {}).get("files") or []
    target = next((f for f in files if f["name"].endswith("-ecospold1.zip")), None)
    if not target or not (archive or download):
        return None
    when = (record.get("run") or {}).get("started") or (record.get("local") or {}).get("started")
    if not when:
        return None
    digest = target["sha256"]
    from release_build.inventory_quality import assess

    def run(path):
        return assess(path, site.root / "quality/criteria.json", expected_digest=digest,
                      year=int(when[:4]), case_codes={str(code) for code in site.datasets})

    if archive:
        return run(archive)
    for release in record.get("releases") or []:
        if any(a["name"] == target["name"] and a.get("sha256") == digest for a in release["assets"]):
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "inventory.zip"
                subprocess.run(["gh", "release", "download", release["tag"], "--repo", site.built_by,
                                "--pattern", target["name"], "--output", str(path)], check=True)
                return run(path)
    return None


def overview(site):
    q = site.quality
    if not q:
        return '<p>No inventory assessment is available for this build. <a href="quality.html">Inventory quality criteria</a></p>'
    return (f'<p><strong>{q["mean"]:.2f} / 1</strong> average inventory quality score across '
            f'{q["graded"]:,} graded datasets. {q["bands"].get("poor", 0):,} received a poor grade. <a href="quality.html">See the grades and measured criteria</a>.</p>')


def detail(site):
    q = site.quality
    intro = (f'<p>The {esc(site.provider)} inventory quality score (IQS) measures five properties of each inventory in the patched '
             'ecoSpold build. The score describes the structure and '
             'documentation of the inventory. A field measurement or an independent study is needed to judge whether '
             'an exchange amount represents real production.</p>')
    if not q:
        return intro + '<p>No matching inventory archive was assessed for this build.</p>'
    band_rows = "".join(f'<tr><th scope="row">{label.capitalize()}</th><td>{q["bands"].get(label, 0):,}</td></tr>'
                        for label in ("excellent", "very good", "good", "fair", "poor", "not enough evidence"))
    check_rows = ""
    for key, (label, why) in CHECKS.items():
        counts = q["criteria"][key]
        check_rows += (f'<tr><th scope="row">{label}</th><td>{why}</td>'
                       + "".join(f'<td>{counts.get(s, 0):,}</td>' for s in ("pass", "warn", "fail", "absent", "not_applicable"))
                       + '</tr>')
    record = site.last_run or {}
    tag = (record.get("summary") or {}).get("tag") or "Untagged build"
    identity = (f'<p><a href="{esc(site.walk_page)}">{esc(tag)}</a> · '
                f'ecoSpold archive <code>{esc(q["archive_sha256"][:12])}</code></p>')
    return (intro + identity + f'<div class="tally"><div><strong>{q["mean"]:.2f} / 1</strong> Average score</div>'
            f'<div><strong>{q["graded"]:,} of {q["datasets"]:,}</strong> Datasets graded</div></div>'
            '<h2>Grades across the build</h2><div class="table-wrap"><table><thead><tr><th>Grade</th><th>Datasets</th></tr>'
            f'</thead><tbody>{band_rows}</tbody></table></div>'
            '<p>The average uses each graded dataset once. Reference products and supplier links each carry twice the weight '
            'of the other checks. A failing check caps the grade at poor. A warning caps it at good. '
            'The displayed numerical score is the weighted mean before the cap.</p>'
            '<h2>What the checks found</h2><div class="table-wrap"><table><thead><tr><th>Criterion</th><th>Evidence</th>'
            '<th>Pass</th><th>Warning</th><th>Fail</th><th>Missing evidence</th><th>Inapplicable</th></tr></thead>'
            f'<tbody>{check_rows}</tbody></table></div>'
            '<h2>Environmental Footprint data quality</h2>'
            f'<p>Of {q["datasets"]:,} inventories, {q["periods"].get("dated",0):,} declare the end year of their data period. '
            f'For {q["periods"].get("past_end_year",0):,}, that year precedes the build year ({q["year"]}). '
            f'The stated geography matches the supplier in {q["supplier_geography"].get("match", 0):,} of '
            f'{q["supplier_geography"].get("comparable", 0):,} inputs with both locations recorded. '
            'A date and location alone cannot establish technological and geographical fit for an intended use. '
            'These checks have no independently graded construction methods, spread evidence or modelling bases '
            'needed to rate precision and included datasets. A full Environmental Footprint rating is unavailable.</p>'
            '<p><a href="cases.html">Inspect evidence by case</a> · <a href="api/v1/inventory-quality.json">Download the measurements</a></p>')


def case_summary(site, f):
    q = site.quality or {}
    results = q.get("case_datasets", {})
    body = []
    for dataset in f["datasets"]:
        result = results.get(str(dataset["code"]))
        if not result or dataset.get("role", "subject") != "subject":
            continue
        score = f'{result["score"]:.2f} / 1' if result["score"] is not None else "Unscored"
        issues = [name for key, (name, _) in CHECKS.items() if result["criteria"][key] in ("fail", "warn")]
        body.append(f'<li>{esc(dataset["name"])} ({esc(dataset["location"])}) · {score} · {esc(result["band"])}'
                    + (f' · review {esc(", ".join(issues).lower())}' if issues else "") + '</li>')
    return ('<h2>Inventory quality in the patched build</h2><ul>' + "".join(body) +
            '</ul><p><a href="../quality.html">How the inventory grades were measured</a></p>') if body else ""
