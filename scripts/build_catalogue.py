"""Refresh the public browse index using ADEME's open food table and foreground metadata."""

import csv
import hashlib
import json
import lzma
import math
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


# Stable indicator IDs shared with the step explorer and the corresponding ADEME API fields.
IMPACTS = {
    "climate": "Changement_climatique",
    "ozone": "Appauvrissement_de_la_couche_d'ozone",
    "radiation": "Rayonnements_ionisants",
    "photo_ox": "Formation_photochimique_d'ozone",
    "pm": "Particules_fines",
    "ht_nc": "Effets_toxicologiques_sur_la_santé_humaine___substances_non-cancérogènes",
    "ht_c": "Effets_toxicologiques_sur_la_santé_humaine___substances_cancérogènes",
    "acid": "Acidification_terrestre_et_eaux_douces",
    "e_fw": "Eutrophisation_eaux_douces",
    "e_m": "Eutrophisation_marine",
    "e_t": "Eutrophisation_terrestre",
    "ecotox": "Écotoxicité_pour_écosystèmes_aquatiques_d'eau_douce",
    "land": "Utilisation_du_sol",
    "water": "Épuisement_des_ressources_eau",
    "energy": "Épuisement_des_ressources_énergétiques",
    "mater": "Épuisement_des_ressources_minéraux",
    "cc_bio": "Changement_climatique_-_émissions_biogéniques",
    "cc_fos": "Changement_climatique_-_émissions_fossiles",
    "cc_luc": "Changement_climatique_-_émissions_liées_au_changement_d'affectation_des_sols",
}


def published_foods():
    with urlopen(API, timeout=30) as response:
        metadata = json.load(response)
    if "3.2" not in metadata["description"] or "Open Licence" not in metadata["license"]["title"]:
        raise ValueError("Check the release and terms of ADEME’s food table")
    schema = {field["key"]: field for field in metadata["schema"]}
    fields = [*FIELDS, *IMPACTS.values()]
    query = urlencode({"size": 1000, "select": ",".join(fields), "sort": "Code_AGB"})
    url = f"{API}/lines?{query}"
    rows = []
    scores = {}
    total = None
    while url:
        with urlopen(url, timeout=30) as response:
            page = json.load(response)
        if total is None:
            total = page["total"]
        for record in page["results"]:
            food = [str(record[key]).strip() for key in FIELDS]
            rows.append(food)
            values = [record.get(key) for key in IMPACTS.values()]
            if any(v is not None and not math.isfinite(v) for v in values):
                raise ValueError(f"Invalid public score for {food[2]}")
            scores[food[2]] = values
        url = page.get("next")
    if len(rows) != total or len(scores) != total:
        raise ValueError("Incomplete food table or duplicate AGRIBALYSE identifier")
    # Use the same English labels that readers see in the build comparison.
    run = json.loads((ROOT / "site/licensed-run.json").read_text())["diagnostics"]
    methods = {field["id"]: field for field in run["indicators"]}
    indicators = [
        {
            "id": key, "name": methods[key]["name"],
            "unit": schema[field]["description"].split("/kg de produit")[0].strip()
            or methods[key]["unit"],
        }
        for key, field in IMPACTS.items()
    ]
    return sorted(rows, key=lambda row: (row[1].casefold(), row[2])), {
        "edition": "3.2", "updated": metadata["dataUpdatedAt"][:10], "source": API,
        "indicators": indicators, "scores": scores
    }


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
    food_rows, reference = published_foods()
    catalogue = {"foods": food_rows, "flows": flow_rows, "parameters": parameter_rows}
    for name, data in [("agribalyse-catalogue", catalogue), ("ademe-reference", reference)]:
        path = ROOT / f"site/assets/{name}.json"
        with path.open("w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            stream.write("\n")
    print(", ".join(f"{len(rows):,} {name}" for name, rows in catalogue.items()))
