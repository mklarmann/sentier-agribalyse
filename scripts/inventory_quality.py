# /// script
# requires-python = ">=3.12"
# dependencies = ["sentier-diagnostics"]
# [tool.uv.sources]
# sentier-diagnostics = { git = "https://github.com/sentier-dev/sentier-diagnostics", rev = "43a9efb049baedbd0931647abeebcd076688ad7e" }
# ///
"""Record safe quality evidence from a licensed run and render its rows in the review site."""

import argparse
import csv
import re
from decimal import Decimal, InvalidOperation
import hashlib
import json
import lzma
from collections import Counter
from pathlib import Path

from sentier_diagnostics.quality import ef
from sentier_diagnostics.quality.contract import Absence, Observation, Result, Verdict
from sentier_diagnostics.quality.engine import combine, read_rules

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FIELDS = (
    "Geography",
    "Technology",
    "Time period",
    "Collection method",
    "Representativeness",
)
BEGIN = "<!-- inventory quality measurements -->"
END = "<!-- end inventory quality measurements -->"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def output_evidence(block):
    """Inspect each co-product or waste-treatment reference row of a SimaPro process."""
    sections = re.finditer(r"^(?:Products|Waste treatment)\n((?:[^\n]+\n)+)", block, re.MULTILINE)
    declared = verified = missing = 0
    for section in sections:
        for row in csv.reader(section.group(1).splitlines(), delimiter=";"):
            declared += 1
            if len(row) < 3 or not all(v.strip() for v in row[:3]):
                missing += 1
                continue
            try:
                amount = Decimal(row[2].strip().replace(",", "."))
            except InvalidOperation:
                missing += 1  # a parameter expression requires an evaluated quantity
                continue
            if amount.is_finite() and amount != 0:
                verified += 1
    observations = (
        Observation(
            "verified",
            verified,
            how="count named output rows with a unit and a finite nonzero quantity",
        ),
        Observation("declared", declared, how="count Products and Waste treatment output rows"),
    )
    if not declared or (not verified and missing):
        return Result.absent(
            "source_output",
            Absence.NO_EVIDENCE,
            "{verified} verifiable outputs among {declared} declared rows. Output evidence is incomplete.",
            observations,
        )
    return Result.measured(
        "source_output",
        Verdict.PASS if verified else Verdict.FAIL,
        float(bool(verified)),
        "{verified} of {declared} declared outputs have a name, a unit and a finite nonzero quantity.",
        observations,
        evaluated=declared,
    )


def collect(tree, record):
    """Allowlisted counts only. Check that this inventory is the one in the public run."""
    import subprocess

    commit = subprocess.check_output(
        ["git", "-C", str(tree), "rev-parse", "HEAD"], text=True
    ).strip()
    if commit != record["local"]["commit"]:
        raise ValueError("The working tree and the reviewed run have different revisions")
    with lzma.open(tree / "source/AGB32_ecoinvent_free.CSV.xz", "rb") as stream:
        raw = stream.read()
    sha = hashlib.sha256(raw).hexdigest()
    if not any(sha in line for _, line in record["transcript"]["lines"]):
        raise ValueError("The shipped export differs from the recorded run")
    # SimaPro's process metadata uses an exact field heading followed by its text.
    # Count one declared field per process. Keep the observations, never the free text.
    totals = Counter()
    outputs = Counter()
    bands = Counter()
    rules = read_rules(
        ROOT / "site/inventory-quality-rules.json", shown="inventory-quality-rules.json"
    )
    processes = 0
    for block in raw.decode("latin-1").replace("\r\n", "\n").split("\nProcess\n")[1:]:
        header = re.split(r"\n(?:Products|Waste treatment)\n", block, maxsplit=1)[0].splitlines()
        result = output_evidence(block)
        outputs[result.said] += 1
        bands[combine([result], rules).said] += 1
        processes += 1
        seen = set()
        for field, value in zip(header, header[1:]):
            if field in SOURCE_FIELDS and value.strip().casefold() not in (
                "",
                "unspecified",
                "unknown",
                "none",
            ):
                seen.add(field)
        totals.update(seen)
    expected = next(
        f["value"] for f in record["summary"]["steps"][0]["figures"] if f["label"] == "processes"
    )
    if expected != processes:
        raise ValueError("The source metadata scan missed a process")
    stages = read_json(tree / "dashboard/run_report.json")["stages"]
    audit = read_json(tree / "dashboard/characterization_audit.json")
    if audit["candidate_content_hash"] != stages["scoring_package"]["content_hash"]:
        raise ValueError("The inventory and factor coverage audit refer to different packages")
    return {
        "commit": commit,
        "source_sha256": sha,
        "inventory_hash": audit["candidate_content_hash"],
        "flow_audit": {
            "methods": audit["climate_methods_audited"],
            "failed": len(audit["failed_methods"]),
        },
        "processes": processes,
        "source_outputs": {key: outputs[key] for key in ("pass", "fail", "absent")},
        "source_output_standings": dict(bands),
        "metadata": {f: totals[f] for f in SOURCE_FIELDS},
    }


def factor_coverage(data):
    count, failed = data["methods"], data["failed"]
    if not (isinstance(count, int) and isinstance(failed, int) and 0 <= failed <= count):
        raise ValueError("Invalid audited climate method counts")
    if not count:
        return Result.absent(
            "climate_factors", Absence.NO_EVIDENCE, "The build did not evaluate a climate method."
        )
    return Result.measured(
        "climate_factors",
        Verdict.FAIL if failed else Verdict.PASS,
        (count - failed) / count,
        "{failed} of {methods} audited climate methods failed the required greenhouse-gas coverage check.",
        [
            Observation(
                "failed", failed, how="number of failed methods in the final characterization audit"
            ),
            Observation("methods", count, at="characterization_audit.json:climate_methods_audited"),
        ],
        evaluated=count,
    )


def climate_agreement(step):
    figures = {f["label"]: f["value"] for f in step["figures"]}
    n = figures.get("climate scores compared", 0)
    within = figures.get("climate scores within 5%")
    if not n or within is None:
        return Result.absent(
            "climate_agreement",
            Absence.NO_EVIDENCE,
            "The record contains no comparable climate score count.",
        )
    if not 0 <= within <= n:
        raise ValueError("Invalid count of comparable climate scores")
    pct = within * 100 / n
    return Result.measured(
        "climate_agreement",
        Verdict.PASS if pct >= 99 else Verdict.FAIL,
        within / n,
        "{within} of {compared} climate scores fall within 5% of ADEME ({percent}%). The acceptance target is {target}%.",
        [
            Observation("within", within, at="licensed-run.json:Score figures"),
            Observation("compared", n, at="licensed-run.json:Score figures"),
            Observation("percent", round(pct, 1), how="100 times within divided by compared"),
            Observation("target", 99, at="licensed-run.json:climate acceptance criterion"),
        ],
        evaluated=n,
    )


def render(owned, record):
    if owned["commit"] != record["local"]["commit"]:
        raise ValueError("The evidence and the review record must name the same build")
    stage = next(s for s in record["summary"]["steps"] if s["name"] == "Score")
    evidence = owned["metadata"]
    # Counts of free-text fields establish availability only. They do not classify the
    # sampled products under the workbench's method tiers or the connection protocol.
    own_ef = ef.own_quality(
        {
            "inventory_precision": ef.inventory_precision(),
            "inventory_representativeness": ef.representativeness(),
            "connection_representativeness": ef.connection_from_basis(None, year_asked=False),
        }
    )
    outputs = owned["source_outputs"]
    if sum(outputs.values()) != owned["processes"]:
        raise ValueError("Source output results omit or double-count a process")
    results = [factor_coverage(owned["flow_audit"]), climate_agreement(stage), own_ef]
    rules = read_rules(
        ROOT / "site/inventory-quality-rules.json", shown="inventory-quality-rules.json"
    )
    standing = combine(results, rules)
    titles = [
        "Required climate factors",
        "Reproduction of climate results",
        "Evidence for an EF data-quality rating",
    ]
    lines = [
        "## Measured inventory checks",
        "",
        f"Revision `{owned['commit'][:7]}`. The review has evidence for {standing.measured_weight:g} of {standing.applicable_weight:g} equally weighted checks.",
        "",
        "| Check | Result | Observation |",
        "|---|---|---|",
    ]
    for title, result in zip(titles, results, strict=True):
        lines.append(f"| {title} | {result.said.capitalize()} | {result.reason} |")
    lines += [
        "",
        "### Reference outputs in the source inventories",
        "",
        f"Of {owned['processes']:,} source processes, {outputs['pass']:,} have at least one named product or waste-treatment output with a unit and an explicit, finite, nonzero quantity. {outputs['fail']:,} fail this check and {outputs['absent']:,} have insufficient evidence. Co-products are assessed together within their process. A parameter or formula requires its evaluated quantity before it can pass. The unit’s suitability and the amount’s accuracy require further evidence.",
        "",
        "### What the AGRIBALYSE source documents",
        "",
        f"Across {owned['processes']:,} source processes, {evidence['Geography']:,} declare geography, {evidence['Technology']:,} declare technology and {evidence['Time period']:,} declare a time period. {evidence['Collection method']:,} describe collection methods and {evidence['Representativeness']:,} include a representativeness statement.",
        "",
        "These counts locate evidence for a reviewer. Assigning a product rating requires a documented sampling or estimation basis, independently assessed fit to the product, and the modelling basis of the included datasets. The current review record has no verified ratings for those inputs.",
    ]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--from-build",
        type=Path,
        help="refresh the allowlisted evidence from the reviewed licensed build",
    )
    p.add_argument(
        "--check",
        action="store_true",
        help="check that the committed review page matches the evidence",
    )
    args = p.parse_args()
    record = read_json(ROOT / "site/licensed-run.json")
    path = ROOT / "site/inventory-quality-evidence.json"
    evidence = collect(args.from_build, record) if args.from_build else read_json(path)
    page = ROOT / "community/build-validation.md"
    old = page.read_text()
    prefix, rest = old.split(BEGIN, 1)
    _, suffix = rest.split(END, 1)
    updated = prefix + BEGIN + "\n\n" + render(evidence, record) + "\n\n" + END + suffix
    if args.check:
        if updated != old or read_json(path) != evidence:
            p.exit(1, "The quality page differs from the reviewed evidence.\n")
    else:
        if args.from_build:
            path.write_text(json.dumps(evidence, indent=2) + "\n")
        page.write_text(updated)


if __name__ == "__main__":
    main()
