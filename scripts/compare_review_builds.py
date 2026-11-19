"""Generate public, counts-only diagnostics from the local AGRIBALYSE build series.

Supply the baseline, stable-code, flow-matching, water-use and integrated build
directories in order. A repeated baseline or stable-code build measures numerical noise.
"""

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

import pandas as pd
from sentier_diagnostics import chain, page, rule
from config import Settings
from config.paths import Paths
from pipelines.backtest import BacktestPipeline
from reporting.backtest_dashboard_csv import BacktestPass1Emitter

STATES = [
    ("baseline", "Release rebuild", "AGRIBALYSE 3.2 rebuilt from the distributable export."),
    (
        "codes",
        "Stable identifiers",
        "Assign stable identifiers to the same source activities and products.",
    ),
    (
        "flows",
        "Flow compartment matching",
        "Resolve elementary flows using their environmental subcompartment.",
    ),
    ("water", "Regional water use", "Apply the water-use correction to the reconstructed system."),
    (
        "integrated",
        "Integrated review build",
        "Apply the remaining import, coverage, reconstruction and export changes together.",
    ),
]


def load(tree):
    report = json.loads((tree / "dashboard/run_report.json").read_text())["stages"]
    if report["csv_source"]["variant"] != "ecoinvent-free":
        raise ValueError("Expected the distributable AGRIBALYSE export in every build")
    commit = subprocess.check_output(
        ["git", "-C", str(tree), "rev-parse", "HEAD"], text=True
    ).strip()
    with (tree / "source" / report["csv_source"]["file"]).open("rb") as f:
        source = hashlib.file_digest(f, "sha256").hexdigest()
    df = pd.read_parquet(tree / "dashboard/backtest/scores.parquet")
    if df["Code AGB"].isna().any():
        raise ValueError("Missing reference product code")
    df["Code AGB"] = df["Code AGB"].astype(str)
    if df["Code AGB"].duplicated().any():
        raise ValueError("Duplicate reference product code")
    return df.set_index("Code AGB").sort_index(), commit, source


def numbers(df, methods, prefix):
    return {
        key: {
            item: float(x) if pd.notna(x) and math.isfinite(x) else None
            for item, x in df[prefix + key].items()
        }
        for key in methods
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key, _, _ in STATES:
        parser.add_argument("--" + key, required=True, type=Path)
    parser.add_argument("--repeat-baseline", type=Path)
    parser.add_argument("--repeat-codes", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--local-explorer", action="store_true",
        help="Also write the full product explorer under .local/review-explorer in this checkout.",
    )
    args = parser.parse_args()
    data = {k: load(getattr(args, k)) for k, _, _ in STATES}
    baseline, _, sha = data["baseline"]
    methods = [c.removeprefix("reference_") for c in baseline if c.startswith("reference_")]
    reference_path = Path("source/AGRIBALYSE3.2_reference_synthese_raw.parquet")
    reference_hash = hashlib.sha256((args.baseline / reference_path).read_bytes()).hexdigest()
    settings = Settings(paths=Paths(package_root=args.baseline.resolve()))
    raw = BacktestPipeline(settings)._load_ademe_reference().set_index("Code AGB").sort_index()
    if not raw.index.equals(baseline.index):
        raise ValueError("Published reference product codes differ from the baseline")
    reference = numbers(raw, methods, "ademe_")
    # The stable short names are also used by the import's published dashboard.
    method_units = pd.read_parquet(
        args.baseline / "source/AGRIBALYSE3.2_reference_synthese_raw.parquet"
    ).iloc[2]
    indicators = [
        (
            BacktestPass1Emitter.LONG_TO_SHORT[m],
            m.capitalize(),
            m.capitalize()[:28],
            str(method_units[str(col)]).split("/kg")[0].strip(),
        )
        for method, (col, _) in BacktestPipeline.METHOD_TO_ADEME.items()
        if (m := method[2]) in methods
    ]
    ids = {m: BacktestPass1Emitter.LONG_TO_SHORT[m] for m in methods}

    def keyed(table):
        return {ids[m]: table[m] for m in methods}

    values = {"ademe": keyed(reference)}
    states = [
        chain.state(
            "ademe",
            "ADEME reference",
            kind="published",
            about="Published impact scores per kilogram of food in AGRIBALYSE 3.2.",
        )
    ]
    units = {item: "kg of product" for item in baseline.index}
    steps = []
    for key, label, about in STATES:
        frame, commit, checksum = data[key]
        if (
            checksum != sha
            or not frame.index.equals(baseline.index)
            or hashlib.sha256((getattr(args, key) / reference_path).read_bytes()).hexdigest()
            != reference_hash
        ):
            raise ValueError(f"{label} used a different export or reference product table")
        scores = numbers(frame, methods, "computed_")
        values[key] = keyed(scores)
        noise = None
        repeat = getattr(args, "repeat_" + key, None)
        if repeat:
            other, repeat_commit, repeat_sha = load(repeat)
            if (repeat_commit, repeat_sha) != (commit, sha) or not other.index.equals(frame.index):
                raise ValueError(
                    f"{label} replicate used a different revision, export or product set"
                )
            replica = numbers(other, methods, "computed_")
            by = {
                ids[m]: chain.noise_of(
                    scores[m], replica[m], floor=rule.floor_of(reference[m].values())[0]
                )
                for m in methods
            }
            noise = chain.noise(["First execution", "Repeat execution"], by)
        states.append(
            chain.state(
                key,
                label,
                about=about,
                identity={"Adapter revision": commit, "Export SHA-256": sha},
                join={
                    "compared": int(frame.mapped.sum()),
                    "unmatched": int((~frame.mapped.astype(bool)).sum()),
                },
                noise=noise,
            )
        )
        reproduction = key == "baseline"
        steps.append(
            chain.step(
                key,
                "Reproduce ADEME’s results" if reproduction else label,
                kind="reproduction" if reproduction else "build change",
                about=about,
                explained=not reproduction and key != "integrated",
                tolerance=chain.tolerance(
                    0.05 if reproduction else 1e-6,
                    basis="declared",
                    note="Review band for agreement with ADEME."
                    if reproduction
                    else "Relative tolerance for two computed results.",
                ),
            )
        )
    title = "From ADEME’s results to the integrated build"
    options = dict(
        indicators=indicators,
        states=states,
        steps=steps,
        values=values,
        units=units,
        item_word=("product", "products"),
        indicator_word=("indicator", "indicators"),
        about="Follow the same reference products through the ecoinvent 3.9.1 cut-off rebuild. Select an indicator or a build step to see where its results change.",
        notes=[
            "The diagnostic comparison uses the larger absolute score as the denominator and groups near-zero results. The Score stage separately tests a 5% difference relative to ADEME for non-zero reference values.",
            "The integrated step groups the remaining changes. Its results alone cannot attribute a difference to any single amendment.",
        ],
    )
    output = chain.build(title, **options, tier="counts", audience="public")
    chain.write(output, args.out)
    if args.local_explorer:
        names = {
            code: {"name": row["LCI Name"], "group": row["Groupe d'aliment"]}
            for code, row in raw.iterrows()
        }
        local, matrix = chain.build_with_matrix(
            title, **options, tier="items", audience="local", names=names
        )
        folder = Path(__file__).resolve().parents[1] / ".local/review-explorer"
        print(page.write(local, folder, matrix=matrix))


if __name__ == "__main__":
    main()
