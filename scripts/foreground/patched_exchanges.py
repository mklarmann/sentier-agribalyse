"""Export the linked AGRIBALYSE columns of the reviewed stripped inventory as a CSV."""
import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix


def write(bundle, stripped_manifest, output):
    skeleton = next((bundle / "skeleton").glob("*/ids.json")).parent
    ids = json.loads((skeleton / "ids.json").read_text())
    columns = {index: int(key) for key, index in ids["technosphere_col_id_to_idx"].items()}
    reserved = set(json.loads((skeleton / "ecoinvent_slot_cols.json").read_text()))
    expected_slots = sum(len(pd.read_parquet(skeleton / f)) for f in
                         ("ecoinvent_slot_index.parquet", "rebuilt_slot_index.parquet"))
    if len(reserved) != expected_slots or not reserved.issubset(columns):
        raise ValueError("Inconsistent refill columns")
    kept = {value for col, value in columns.items() if col not in reserved}
    removed = {row["identifier"] for row in json.loads(stripped_manifest.read_text())["removed"]}
    activities = pd.read_parquet(bundle / "registry/activity_catalog.parquet")
    activities = activities[activities.activity_id.isin(kept)].set_index("activity_id")
    if (set(activities.index) != kept or not activities.index.is_unique
            or set(activities.database) != {"agribalyse-3.2"} or removed.intersection(activities.code)):
        raise ValueError("Unexpected process in the foreground selection")
    with output.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as zipped:
        with io.TextIOWrapper(zipped, encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["process_id", "process_code", "process_name", "process_unit",
                             "matrix", "row_id", "coefficient"])
            for kind in ("technosphere", "biosphere"):
                row_ids = {index: key for key, index in ids[kind + "_row_id_to_idx"].items()}
                with np.load(skeleton / (kind + ".csr.npz"), allow_pickle=False) as array:
                    matrix = csr_matrix((array["data"], array["indices"], array["indptr"]),
                                        shape=tuple(array["shape"])).tocsc()
                if matrix[:, sorted(reserved)].nnz:
                    raise ValueError(f"Licensed refill column holds {kind} entries")
                for col, aid in columns.items():
                    if col in reserved:
                        continue
                    start, end = matrix.indptr[col:col + 2]
                    activity = activities.loc[aid]
                    for pos in range(start, end):
                        writer.writerow([aid, activity.code, activity["name"], activity.unit,
                                         kind, row_ids[matrix.indices[pos]], float(matrix.data[pos])])
    print(hashlib.sha256(output.read_bytes()).hexdigest(), output.name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("stripped_manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    write(args.bundle, args.stripped_manifest, args.output)
