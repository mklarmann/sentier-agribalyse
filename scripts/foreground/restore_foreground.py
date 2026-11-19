"""Join the published foreground coefficients to a locally rebuilt licensed background."""
import json
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix, csr_matrix


def main():
    report = json.loads(Path("dashboard/run_report.json").read_text())
    package = Path("cache/scoring_packages") / report["stages"]["scoring_package"]["content_hash"]
    ids = json.loads((package / "ids.json").read_text())
    table = pd.read_csv("patched-foreground-exchanges.csv.gz", usecols=["process_id", "matrix", "row_id", "coefficient"],
                        dtype={"process_id": str, "row_id": str}, float_precision="round_trip")
    table["column"] = table.process_id.map(ids["technosphere_col_id_to_idx"])
    if table.column.isna().any() or table.duplicated(["matrix", "process_id", "row_id"]).any():
        raise ValueError("The foreground process identifiers do not match the build, or an exchange is duplicated")
    if set(table.matrix) != {"technosphere", "biosphere"}:
        raise ValueError("Expected technosphere and biosphere foreground exchanges")
    columns = table.column.unique()
    with tempfile.TemporaryDirectory(dir=package) as scratch:
        paths = []
        for kind in ("technosphere", "biosphere"):
            path = package / (kind + ".csr.npz")
            with np.load(path, allow_pickle=False) as source:
                original = csr_matrix((source["data"], source["indices"], source["indptr"]), shape=tuple(source["shape"]))
            data = table[table.matrix == kind]
            rows = data.row_id.map(ids[kind + "_row_id_to_idx"])
            if rows.isna().any():
                raise ValueError(f"Unknown {kind} row identifier in foreground")
            foreground = coo_matrix((data.coefficient, (rows, data.column)), shape=original.shape).tocsr()
            background = original.tocoo()
            keep = ~np.isin(background.col, columns)
            retained = coo_matrix((background.data[keep], (background.row[keep], background.col[keep])),
                                  shape=original.shape).tocsr()
            combined = retained + foreground
            if (combined != original).nnz:
                raise ValueError(f"The reconstructed {kind} matrix differs from the source rebuild")
            ready = Path(scratch) / path.name
            np.savez_compressed(ready, data=combined.data, indices=combined.indices,
                                indptr=combined.indptr, shape=combined.shape)
            paths.append((ready, path))
            print(f"{kind}: restored {len(data)} published coefficients; every joined coefficient verified")
        for ready, path in paths:
            ready.replace(path)
    print(f"Restored {len(columns)} foreground processes against the locally supplied background")


if __name__ == "__main__":
    main()
