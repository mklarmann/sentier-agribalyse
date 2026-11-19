"""Rebuild the published food scores inside an extracted AGRIBALYSE foreground kit."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from urllib.parse import quote
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
LICENSED = (
    "ecoinvent-3.9.1-cutoff-exchanges.parquet", "ecoinvent-3.9.1-cutoff-activities.json",
    "ecoinvent-3.9.1-biosphere-flows.json", "ef-v31-methods.json",
)
STEPS = (
    "dds-fetch-harmonised-flows", "dds-build-registry", "dds-build-ef-flows-registry",
    "dds-build-biosphere-catalog", "dds-build-method-cfs-registry",
    "dds-build-ecoinvent-catalog", "dds-link-all",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--licensed-source", type=Path, help="Reuse locally prepared 3.9.1 cut-off snapshots")
    parser.add_argument("--umfpack", action="store_true", help="Use the same sparse solver as the review build (needs SuiteSparse)")
    args = parser.parse_args()
    os.chdir(ROOT)
    manifest = json.loads(Path("inputs.json").read_text())
    for name, sha in manifest["included"].items():
        if digest(Path(name)) != sha:
            raise SystemExit(f"Kit checksum differs for {name}")
    for name, sha in manifest["public_inputs"].items():
        path = Path(name)
        if not path.exists() or digest(path) != sha:
            url = manifest["public_source"] + "/" + quote(name)
            path.parent.mkdir(exist_ok=True, parents=True)
            with urlopen(url, timeout=120) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != sha:
                raise SystemExit(f"Downloaded input differs from the review build: {name}")
            path.write_bytes(data)
    extras = []
    if args.umfpack:
        extras.extend(["--extra", "umfpack"])
    if not args.licensed_source:
        extras.extend(["--extra", "bootstrap"])
    subprocess.run(["uv", "sync", "--frozen", "--python", "3.12", *extras], check=True)
    def run(cmd, *args):
        subprocess.run(["uv", "run", "--no-sync", cmd, *args], check=True)
    if args.licensed_source:
        for name in (*LICENSED, "harmonised-flows-simple.json.gz"):
            src = args.licensed_source.resolve() / name
            dst = ROOT / "source" / name
            if name not in LICENSED and not src.is_file():
                continue
            if not src.is_file():
                raise SystemExit(f"Missing licensed input {src}")
            if not dst.exists() or not src.samefile(dst):
                shutil.copyfile(src, dst)
    else:
        run("dds-bootstrap-ecoinvent")
    for step in STEPS:
        run(step)
    run("python", "restore_foreground.py")
    run("dds-backtest", "--solver", "scipy")
    run("python", "verify_food_scores.py")


if __name__ == "__main__":
    main()
