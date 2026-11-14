"""Machine-readable outputs for other projects: coordination data only, no inventory rows.

Inside api/v1 a field is never renamed or removed; fields may be added.
"""

import json

import community


def finding_summary(site, f):
    """One finding for api/v1/findings.json: coordination fields only, absolute addresses."""
    base = site.config["site_url"]
    dates = {name: (f[name] or {}).get("date") for name in community.EVIDENCE}
    return {
        "id": f["id"],
        "issue": f["issue"],
        "title": f["title"],
        "kind": f["kind"],
        "status": f["stage"],
        "status_label": site.label(f["stage"]),
        "datasets": [d["code"] for d in f["datasets"]],
        "scope": f["scope"],
        "releases": f["releases"],
        "patches": [x["id"] for x in f["patches"]],
        "answer_outcome": f["answer"]["outcome"] if f["answer"] else None,
        "reported": dates["reported"],
        "repeated": dates["repeated"],
        "sent": dates["sent"],
        "answered": dates["answer"],
        "fixed": dates["fixed_in"],
        "closed": dates["closed"],
        "changed": f["changed"],
        "waiting_since": f["waiting_since"],
        "url": f'{base}findings/{f["id"]}.html',
        "json": f'{base}api/v1/findings/{f["id"]}.json',
    }


def write_data(site):
    placed = sorted(site.triage["findings"], key=community.finding_number)
    base, counts = site.config["site_url"], site.triage["counts"]
    identity = {"generated": site.built, "revision": site.revision, "site": base}
    site.write_json("api/v1/findings.json", {
        "schema": "sentier-bafu/findings/1",
        **identity,
        "statuses": community.statuses(site.provider),
        "findings": [finding_summary(site, f) for f in placed],
    }, one_per_line="findings")
    for f in placed:
        summary = finding_summary(site, f)
        site.write_json(f'api/v1/findings/{f["id"]}.json', {
            "schema": "sentier-bafu/finding/1",
            **identity,
            "record": {key: f[key] for key in community.FINDING_FIELDS},
            "status": f["stage"],
            "status_label": summary["status_label"],
            "patches": f["patches"],
            "related": f["related"],
            "changed": f["changed"],
            "waiting_since": f["waiting_since"],
            "discussion": f["tracker"],
            "url": summary["url"],
            "source": f'{site.source_repo}/blob/{site.ref}/{f["path"]}',
        })
    site.write_json("api/v1/datasets.json", {
        "schema": "sentier-bafu/datasets/1",
        **identity,
        "roles": community.DATASET_ROLES,
        "datasets": {str(code): entry for code, entry in site.datasets.items()},
    }, one_per_line="datasets")
    site.write_json("api/v1/contributions.json", {
        "schema": "sentier-bafu/contributions/1",
        **identity,
        "classes": [
            {k: v.format(provider=site.provider) for k, v in c.items()} for c in community.CONTRIBUTION_CLASSES
        ],
        "contributions": [
            {
                "id": c["id"],
                "issue": c["issue"],
                "title": c["title"],
                "class": c["class"],
                "status": c["status"],
                "url": f'{base}contributions/{c["id"]}.html',
            }
            for c in site.contributions
        ],
    })
    status = {
        "dataset": site.dataset,
        "findings": len(placed),
        "findings_by_stage": counts,
        "contributions": len(site.contributions),
        "accepted": sum(c["status"] == "accepted" for c in site.contributions),
        "source_ref": site.ref,
        "revision": site.revision,
        "built": site.built,
        "issues": site.issues_source,
        "preview": bool(site.preview_url) or bool(getattr(site, "elsewhere", False)),
    }
    site.write_json("api/v1/status.json", {
        "schema": "sentier-bafu/status/1",
        **status,
        "findings_by_status": {s["key"]: counts.get(s["key"], 0) for s in community.STATUSES},
        "patches": len((site.patches or {}).get("patches", [])),
    })
    for name in ("finding", "contribution"):
        site.write(f"schema/{name}.schema.json", (site.root / f"schema/{name}.schema.json").read_text())
    # The one-line-per-finding table is a build output, never a committed file.
    site.write("ledger.md", community.index_text(placed, site.records_config))
    # Kept at the root, in their earlier shape, for readers that have not moved to api/v1.
    site.write_json("findings.json", [
        dict(id=f["id"], title=f["title"], status=f["stage"], stage=f["stage"],
             release=community.release_names(f, site.records_config),
             links=community.discussion_links(f, site.repo), page=f'findings/{f["id"]}.html')
        for f in placed
    ])
    site.write("status.json", json.dumps(status, indent=2) + "\n")
