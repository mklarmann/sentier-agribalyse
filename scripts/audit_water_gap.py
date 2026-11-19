"""Reproduce the water investigation from local licensed builds. Output is aggregate only.

Use the integrated adapter's Python environment and src on PYTHONPATH.
Pass the directory containing the fb-nb-* and fb-col-* builds and the paired
full-source adapter directory. --write refreshes the study on the Comparison page.
"""

import argparse
import hashlib
import json
import lzma
import subprocess
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import load_workbook
from scoring.simapro_water_use import SimaProWaterUseFactors

from config import Settings
from config.paths import Paths
from pipelines.backtest import BacktestPipeline
from scoring.native_scorer import NativeLciaScorer
from scoring.scoring_package_locator import ScoringPackageLocator
from transforms.ecoinvent_stripper import EcoinventStripper

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "site/water-use.md"
EXPORT = "AGB32_ecoinvent_free.CSV.xz"
SHEET = "EF3.1 (adapted) (1).XLSX"
SYNTHESIS = "AGRIBALYSE3.2_reference_synthese_raw.parquet"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def revision(root):
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()


def report(root):
    return json.loads((root / "dashboard/run_report.json").read_text())["stages"]


def package(root):
    return root / "cache/scoring_packages" / report(root)["scoring_package"]["content_hash"]


def water_scores(root, reference):
    """Return unrounded scores and the reported scores used in the downloadable grid."""
    frame = pd.read_parquet(root / "dashboard/backtest/scores.parquet")
    frame.index = frame["Code AGB"].astype(str)
    require(
        frame.index.is_unique and set(frame.index) == set(reference.index),
        "Food identifiers differ",
    )
    frame = frame.loc[reference.index]
    require(frame.mapped.all(), "A reference food was not mapped")
    recorded = frame["reference_water use"]
    scores = frame["computed_water use"].copy()
    floored = (recorded == 0) & (scores == 0) & (reference != 0)
    require(np.array_equal(recorded[~floored], reference[~floored]), "Published references differ")
    if floored.any():
        pkg = ScoringPackageLocator(Settings(paths=Paths(package_root=root))).load()
        method = next(key for key in pkg.methods if key[2] == "water use")
        scorer = NativeLciaScorer(package=pkg, use_pardiso=False)
        catalogue = pd.read_parquet(root / "registry/product_catalog.parquet").set_index(
            ["database", "code"]
        )
        for code, row in frame[floored].iterrows():
            key = (row.product_db, row.product_code)
            pid = catalogue.loc[key, "product_id"]
            scores[code] = scorer.score([(key, int(pid))], [method])[key].scores[method]
    require(np.isfinite(scores).all(), "Missing or non-finite water score")
    return scores, frame["computed_water use"]


def check_method(root):
    """Read the original workbook independently of the adapter's XLSX parser and its cached table."""
    source = root / "source"
    factors = SimaProWaterUseFactors.from_table(
        pd.read_parquet(source / "simapro-EF31-adapted-cfs.parquet")
    )
    wb = load_workbook(source / SHEET, read_only=True, data_only=True)
    expected = {}
    try:
        active = False
        for row in wb["Sheet1"].iter_rows(max_col=6, values_only=True):
            comp, sub, flow, _, cf, unit = row
            if comp == "Impact category":
                active = sub == "Water use"
            elif active and isinstance(cf, (int, float)) and comp:
                key = (comp, sub or "", flow)
                require(key not in expected, "Duplicate water factor")
                expected[key] = cf * {"kg": 1000, "m3": 1}[unit]
    finally:
        wb.close()
    require(expected and expected == dict(factors.per_m3), "Water factors differ from the workbook")
    for region in ("FR", "US"):
        withdrawal = factors.for_name("Raw", "(unspecified)", f"Water, river, {region}")
        surface = factors.for_name("Water", "river", f"Water, {region}")
        ocean = factors.for_name("Water", "ocean", f"Water, {region}")
        require(
            withdrawal > 0 and surface == -withdrawal and ocean == 0,
            "Water return or withdrawal mismatch",
        )
    return len(expected)


def median_gap(values):
    return (values.median() - 1) * 100


def within(values):
    return int(((values - 1).abs() <= 0.05).sum())


def audit(builds, full):
    def tree(name):
        return builds / ("fb-" + name + "-adapter")

    before, water, final = (tree(k) for k in ("nb-ac", "nb-acw", "review-nov18"))
    controls = [tree(k) for k in ("col-h-full", "col-h-v041", "nb-h")]
    old_full = tree("col-main-full")
    chain = json.loads((ROOT / "site/licensed-run.json").read_text())["diagnostics"]
    stages = [tree("nb-main-a"), tree("nb-a"), before, water, final]
    require(
        [revision(t) for t in stages]
        == [s["identity"]["Adapter revision"] for s in chain["states"][1:]],
        "Stage revisions differ from the published comparison",
    )
    require(
        revision(final) == revision(full) and len({revision(t) for t in controls}) == 1,
        "Source controls must use the same adapter",
    )
    require(
        [report(t)["csv_source"]["variant"] for t in controls]
        == ["full", "ecoinvent-free", "ecoinvent-free"]
        and report(full)["csv_source"]["variant"] == "full",
        "Unexpected source format",
    )
    all_trees = set(stages + controls + [full, old_full])
    for name in (
        SHEET,
        SYNTHESIS,
        "ecoinvent-3.9.1-cutoff-exchanges.parquet",
        "ef-v31-methods.json",
    ):
        require(
            len({sha(t / "source" / name) for t in all_trees}) == 1,
            f"Control input differs: {name}",
        )
    for name in ("ids.json", "technosphere.csr.npz", "biosphere.csr.npz"):
        require(
            sha(package(before) / name) == sha(package(water) / name),
            f"Inventory changed at Step 3: {name}",
        )
    require(
        sha(full / "source/AGB32_final.CSV")
        == sha(controls[0] / "source/AGB32_final.CSV")
        == sha(old_full / "source/AGB32_final.CSV"),
        "Full input differs across controls",
    )
    current = lzma.decompress((final / "source" / EXPORT).read_bytes())
    require(
        sha(final / "source" / EXPORT) == sha(controls[2] / "source" / EXPORT),
        "Current input differs",
    )
    old = lzma.decompress((controls[1] / "source" / EXPORT).read_bytes())
    stripped = EcoinventStripper(markers=("Adapted from Ecoinvent",)).strip(old)
    require(
        stripped.stripped == current,
        "The adapted blocks do not account for the entire input change",
    )
    removed = len(stripped.removed)
    source_manifest = json.loads(
        (final / "source/agribalyse-3.2-stripped-ecoinvent-processes.json").read_text()
    )
    require(
        sha(full / "source/AGB32_final.CSV") == source_manifest["full_csv"]["sha256"],
        "Wrong source release",
    )
    require(
        Counter(x["marker"] for x in source_manifest["removed"])["Adapted from Ecoinvent"]
        == removed,
        "Removed process count differs from the manifest",
    )
    factors = check_method(final)
    reference = (
        BacktestPipeline(Settings(paths=Paths(package_root=final)))
        ._load_ademe_reference()
        .set_index("Code AGB")["ademe_water use"]
    )
    require(
        reference.index.is_unique and np.isfinite(reference).all() and (reference != 0).all(),
        "Water ratios need one nonzero, finite reference per food",
    )
    scores = {}
    reported_scores = {}
    for t in all_trees:
        scores[t], reported_scores[t] = water_scores(t, reference)
    ratio = {t: s / reference for t, s in scores.items()}
    require(
        np.allclose(ratio[full], ratio[controls[0]], rtol=1e-8)
        and np.allclose(ratio[final], ratio[controls[2]], rtol=1e-8),
        "Control differs from the integrated comparison",
    )
    # Guard the link between the public six-state grid and the calculations in this note.
    m = json.loads((ROOT / "site/assets/food-scores.json").read_text())
    j = m["of"]["indicators"].index("water") * 6
    require(
        len(m["items"]) == len(reference)
        and {row[0] for row in m["items"]} == set(reference.index),
        "Grid coverage differs",
    )
    for item, values in zip(m["items"], m["values"], strict=True):
        code = item[0]
        public = values[j : j + 6]
        for k in range(1, 6):
            if public[k] == "=":
                public[k] = public[k - 1]
        require(public[0] == reference[code], "Grid uses a different reference")
        for k, t in enumerate(stages, 1):
            require(public[k] == reported_scores[t][code], "Grid uses a different build score")
    closer = int(((ratio[water] - 1).abs() < (ratio[before] - 1).abs()).sum())
    further = int(((ratio[water] - 1).abs() > (ratio[before] - 1).abs()).sum())
    return make_note(ratio, stages, controls, full, old_full, removed, factors, closer, further)


def make_note(ratio, stages, controls, full, old_full, removed, factors, closer, further):
    baseline, codes, flows, water, final = stages
    prior, step, end = [median_gap(ratio[t]) for t in (flows, water, final)]
    require(
        round(median_gap(ratio[baseline]), 1)
        == round(median_gap(ratio[codes]), 1)
        == round(prior, 1)
        and round(step, 1) == round(end, 1),
        "The stage interpretation needs review",
    )
    rows = []
    for label, t in zip(
        (
            "Full licensed export",
            "Earlier export retaining the adapted processes",
            "Current distributable export",
        ),
        controls,
        strict=True,
    ):
        rows.append(f"| {label} | {median_gap(ratio[t]):+.2f}% | {within(ratio[t]):,} |")
    all_foods = len(ratio[final])
    require(within(ratio[full]) == all_foods, "Review the conclusion about the full source")
    return f"""## Water-use gap

**Step 3, Regional water use, widens the median gap from +{prior:.1f}% to +{step:.1f}% against ADEME.** The first rebuild already has the +{prior:.1f}% gap. Matching identifiers and flows leaves it there. Step 3 changes how the build scores water withdrawn and returned in each region. The inventories and their exchange quantities are identical on either side of this step. The final integration leaves the median at +{end:.1f}%.

**The evidence supports keeping the patch.** On ADEME's full licensed export, all {all_foods:,} foods fall within 5% of their published water-use scores with the patch. The earlier unpatched build had {within(ratio[old_full]):,} foods in that range. The largest remaining difference is about {100 * (ratio[full] - 1).abs().max():.2f}%. We also checked all {factors:,} water factors against the adapted EF 3.1 workbook, including their units and how the patch treats river and ocean returns.

| Input scored with the same water patch | Median difference from ADEME | Foods within 5% (of {all_foods:,}) |
|---|---:|---:|
{chr(10).join(rows)}

The earlier export retained {removed} processes that ADEME had adapted from ecoinvent. Removing those processes reproduced the current distributable input byte for byte. With the same background database and scoring method, this moves the median from {abs(median_gap(ratio[controls[1]])):.2f}% below ADEME to {end:.1f}% above. The test isolates the effect of replacing those inventories as a group. How much each replacement contributes is still open.

On the distributable input, Step 3 moves {closer:,} foods closer to ADEME and {further:,} further away. Each percentage compares a food's score with its own ADEME reference before display rounding. The median weights each food equally.

[Explore Step 3](#sd.step=water) · [ADEME's guidance on source formats and regional water use](https://doc.agribalyse.fr/documentation-en/agribalyse-data/data-access) · [Reproduce this check](../scripts/audit_water_gap.py)
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--builds", type=Path, required=True)
    parser.add_argument("--full", type=Path, required=True)
    parser.add_argument(
        "--write", action="store_true", help="Refresh the page instead of verifying it"
    )
    args = parser.parse_args()
    note = audit(args.builds.resolve(), args.full.resolve())
    if args.write:
        STUDY.write_text(note, encoding="utf-8")
    else:
        require(STUDY.read_text(encoding="utf-8") == note, "Checked findings differ from the page")
    print(note)
