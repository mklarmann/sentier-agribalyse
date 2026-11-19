"""Compare the reconstructed food impacts with the scores shown on the review site."""
import json
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    expected = pd.read_csv("patched-food-scores.csv", dtype={"Code AGB": str}, float_precision="round_trip").set_index("Code AGB").sort_index()
    actual = pd.read_parquet("dashboard/backtest/scores.parquet")
    actual["Code AGB"] = actual["Code AGB"].astype(str)
    actual = actual.set_index("Code AGB").sort_index()
    if not actual.index.is_unique or not actual.index.equals(expected.index):
        raise SystemExit("Rebuilt food identifiers differ from the published set")
    scores = actual.loc[:, expected.columns].to_numpy(dtype=float)
    reference = expected.to_numpy(dtype=float)
    # Relative error per product and indicator. Missing values must be missing on both sides.
    same = np.isclose(scores, reference, rtol=1e-5, atol=0, equal_nan=True)
    print(json.dumps({"foods": len(expected), "indicators": len(expected.columns),
                      "score_cells": int(same.size), "outside_relative_tolerance_1e-5": int((~same).sum())}))
    if not same.all():
        raise SystemExit("The rebuilt results differ. Inspect dashboard/backtest/scores.parquet.")


if __name__ == "__main__":
    main()
