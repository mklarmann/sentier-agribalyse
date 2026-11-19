"""Package the stripped source, the reviewed adapter and food scores from the integrated run."""
import argparse
import hashlib
import io
import json
import lzma
from pathlib import Path
import subprocess
import zipfile

import pandas as pd

HERE = Path(__file__).resolve().parent
SOURCE = "source/AGB32_ecoinvent_free.CSV.xz"
MANIFEST = "source/agribalyse-3.2-stripped-ecoinvent-processes.json"
PUBLIC_INPUT_REV = "542ae8d4829807c7090560693f04f59460f9e6fb"
PUBLIC_INPUT_URL = "https://raw.githubusercontent.com/mklarmann/sentier-agribalyse/" + PUBLIC_INPUT_REV
ADAPTER = "2f7f8f3ecbf8886eef1152bf24bcd5276b04a5bc"
STRIPPED_SHA = "54dc5fcd61f65bdbd0f73fbf7aded26f964f73ea2efcb93f7d741cdc87cdf559"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def package(adapter, exchanges, out):
    def git(*args):
        return subprocess.check_output(["git", "-C", adapter, *args])
    if git("rev-parse", "HEAD").decode().strip() != ADAPTER:
        raise ValueError("Expected the integrated adapter revision")
    def blob(name):
        return git("show", f"{ADAPTER}:{name}")
    members = {name: blob(name) for name in (
        SOURCE, MANIFEST, "source/water-use-bio3-bridge.json", "pyproject.toml", "uv.lock",
        "LICENSE", "BOOTSTRAP.md",
    )}
    for name in git("ls-tree", "-r", "--name-only", ADAPTER, "src").decode().splitlines():
        if name.endswith(".py"):
            members[name] = blob(name)
    stripped = lzma.decompress(members[SOURCE])
    manifest = json.loads(members[MANIFEST])
    if sha(stripped) != STRIPPED_SHA or sha(stripped) != manifest["stripped_csv"]["sha256"]:
        raise ValueError("Foreground differs from the reviewed stripped export")
    # Check the actual product line of each process block, allowing supplier references in inputs.
    previous = b""
    for line in io.BytesIO(stripped):
        line = line.strip()
        if previous in (b"Products", b"Waste treatment"):
            product = line.split(b";", 1)[0].lower()
            if b"copied from ecoinvent" in product or b"adapted from ecoinvent" in product:
                raise ValueError("Embedded ecoinvent process in the compressed inventory")
        previous = line
    public = {}
    for name in git("ls-tree", "-r", "--name-only", ADAPTER, "source").decode().splitlines():
        if name not in members:
            if git("rev-parse", f"{ADAPTER}:{name}") != git("rev-parse", f"{PUBLIC_INPUT_REV}:{name}"):
                raise ValueError(f"Public input differs for {name}")
            public[name] = sha(blob(name))
    members["patched-foreground-exchanges.csv.gz"] = exchanges.read_bytes()
    if sha(members["patched-foreground-exchanges.csv.gz"]) != "ef2d03dc7c9f23b38609258f8ce0e76c918de51ccf2ce8355f79200970c65ef8":
        raise ValueError("The linked foreground differs from the reviewed stripped-matrix export")
    for name in ("rebuild.py", "restore_foreground.py", "verify_food_scores.py", "README.txt"):
        members[name] = (HERE / name).read_bytes()
    scores = pd.read_parquet(adapter / "dashboard/backtest/scores.parquet")
    columns = [name for name in scores if name.startswith("computed_")]
    if len(columns) != 19 or len(scores) != 2451 or not scores["Code AGB"].is_unique:
        raise ValueError("Unexpected score table for the review build")
    members["patched-food-scores.csv"] = scores.sort_values("Code AGB")[["Code AGB", *columns]].to_csv(index=False).encode()
    metadata = {"adapter_revision": ADAPTER, "background": "ecoinvent 3.9.1 cut-off",
                "public_source": PUBLIC_INPUT_URL, "public_inputs": public,
                "included": {name: sha(data) for name, data in sorted(members.items())}}
    members["inputs.json"] = (json.dumps(metadata, indent=2) + "\n").encode()
    with zipfile.ZipFile(out, "w") as archive:
        for name, data in sorted(members.items()):
            entry = zipfile.ZipInfo(name)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, data)
    print(f"{sha(out.read_bytes())}  {out.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("adapter", type=Path)
    parser.add_argument("exchanges", type=Path, help="CSV from patched_exchanges.py")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    package(args.adapter, args.exchanges, args.output)
