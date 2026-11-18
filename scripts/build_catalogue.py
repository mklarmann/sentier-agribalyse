"""Refresh the public browse index using ADEME's open food table and foreground metadata."""

import csv
import hashlib
import json
import lzma
import re
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
API = "https://data.ademe.fr/data-fair/api/v1/datasets/agribalyse-31-synthese"
FIELDS = ("Nom_du_Produit_en_Français", "LCI_Name", "Code_AGB", "Code_CIQUAL", "Groupe_d'aliment")
SECTIONS = re.compile(
    r"^(Resources|Emissions to air|Emissions to water|Emissions to soil|Input parameters|Calculated parameters)\n"
    r"((?:[^\n]+\n)+)", re.MULTILINE
)


def foods():
    with urlopen(API, timeout=30) as response:
        if "3.2" not in json.load(response)["description"]:
            raise ValueError("Check the ADEME food table release before refreshing")
    query = urlencode({"size": 1000, "select": ",".join(FIELDS), "sort": "Code_AGB"})
    url = f"{API}/lines?{query}"
    rows = []
    total = None
    while url:
        with urlopen(url, timeout=30) as response:
            page = json.load(response)
        if total is None:
            total = page["total"]
        rows.extend([str(record[key]).strip() for key in FIELDS] for record in page["results"])
        url = page.get("next")
    if len(rows) != total or len({r[2] for r in rows}) != len(rows):
        raise ValueError("Incomplete food table or duplicate AGRIBALYSE identifier")
    return sorted(rows, key=lambda row: (row[1].casefold(), row[2]))


def foreground_labels():
    flows = set()
    parameters = set()
    with lzma.open(ROOT / "source/AGB32_ecoinvent_free.CSV.xz", "rb") as stream:
        raw = stream.read()
    evidence = json.loads((ROOT / "site/inventory-quality-evidence.json").read_text())
    if hashlib.sha256(raw).hexdigest() != evidence["source_sha256"]:
        raise ValueError("Foreground export differs from the reviewed build")
    processes = raw.decode("latin-1").replace("\r\n", "\n").split("\nProcess\n")
    for process in processes[1:]:
        # The stripped release still has empty process shells from other libraries.
        # Read only the release's own namespace, and never publish exchange or parameter values.
        if not re.search(r"^Process identifier\nAGRIBALU[0-9]+$", process, re.MULTILINE):
            continue
        inventory = process.partition("\nEnd\n")[0]
        for section in SECTIONS.finditer(inventory):
            kind = section[1]
            for row in csv.reader(section[2].rstrip("\n").split("\n"), delimiter=";"):
                if len(row) < 3 or not row[0].strip():
                    raise ValueError(f"Unexpected foreground metadata format in {kind}")
                if kind.endswith("parameters"):
                    parameters.add((row[0].strip(), kind.split()[0]))
                else:
                    flows.add((row[0].strip(), kind, row[1].strip(), row[2].strip()))
    if not flows or not parameters:
        raise ValueError("Missing foreground metadata")
    return sorted(flows), sorted(parameters)


if __name__ == "__main__":
    flow_rows, parameter_rows = foreground_labels()
    catalogue = {"foods": foods(), "flows": flow_rows, "parameters": parameter_rows}
    path = ROOT / "site/assets/agribalyse-catalogue.json"
    with path.open("w", encoding="utf-8") as stream:
        json.dump(catalogue, stream, ensure_ascii=False, separators=(",", ":"))
        stream.write("\n")
    print(", ".join(f"{len(rows):,} {name}" for name, rows in catalogue.items()))
