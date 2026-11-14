"""The import run: what of the import can run in public, and its own account of it.

The import has six stages. One needs nothing but the repository: reading ADEME's export as it
is shipped, without the ecoinvent datasets it carried. The other five need an ecoinvent 3.9.1
licence and run on a licensed machine only. This script runs the first for real and names
the others as "not run here", with the reason. It writes the run's own account (run.json,
format sentier/run/1), which the page "Import and build" shows step by step.

    python3 scripts/import_run.py --out run.json

Every line a step prints begins with the step's name in brackets; the page files the lines
under the steps by that. Standard library only, so that it runs before anything is installed.
Nothing of the ecoinvent background is read, and no value of the export is printed: counts,
sizes and checksums only.
"""

import argparse
import hashlib
import json
import lzma
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runrecord import summary  # noqa: E402

EXPORT = "source/AGB32_ecoinvent_free.CSV.xz"
MANIFEST = "source/agribalyse-3.2-stripped-ecoinvent-processes.json"
FIRST = "ADEME's export"
# The stages a licence is needed for, in the order of the import. The words for each are in
# site/run-steps.json; a test holds the two lists together.
LICENSED = ("Licensed files", "Registry", "Link", "Score", "Export")
NEEDS_LICENCE = "Needs an ecoinvent 3.9.1 licence. It runs on a licensed machine, not here."


def say(step, text):
    print(f"[{step}] {text}", flush=True)


def read_export(root=ROOT):
    """Read the shipped export and compare it with what its manifest records.

    Returns (figures, notes, problems). Nothing is changed and nothing is written.
    """
    root = Path(root)
    manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    shipped = (root / EXPORT).read_bytes()
    say(FIRST, f"{EXPORT}: {len(shipped):,} bytes as shipped")
    export = lzma.decompress(shipped)
    checksum = hashlib.sha256(export).hexdigest()
    say(FIRST, f"unpacked: {len(export):,} bytes, sha256 {checksum}")
    processes = sum(1 for line in export.decode("latin-1").split("\n") if line.strip() == "Process")
    removed = len(manifest["removed"])
    say(FIRST, f"{processes:,} processes in the export; {removed:,} ecoinvent datasets were taken out before it was shipped")
    recorded = manifest["stripped_csv"]
    problems = []
    if checksum != recorded["sha256"]:
        problems.append("The export is not the file its manifest records: the checksums differ.")
    if len(export) != int(recorded["bytes"]):
        problems.append(f"The export has {len(export):,} bytes; its manifest records {int(recorded['bytes']):,}.")
    if processes != int(manifest["processes"]["kept"]):
        problems.append(f"The export holds {processes:,} processes; its manifest records {int(manifest['processes']['kept']):,}.")
    if removed != int(manifest["processes"]["removed"]):
        problems.append(f"The manifest lists {removed:,} removed datasets and says {int(manifest['processes']['removed']):,}.")
    say(FIRST, "the export is the file its manifest records" if not problems else "the export differs from its manifest")
    figures = [(processes, "processes"), (removed, "ecoinvent datasets taken out"), (len(shipped), "bytes shipped")]
    notes = [f"Checked against `{MANIFEST}`: checksum `{checksum}`. Nothing in the export is changed."]
    return figures, notes, problems


def run(root=ROOT):
    """The run's own account: the first stage as it went, the others as not run here."""
    started = time.monotonic()
    try:
        figures, notes, problems = read_export(root)
    except (OSError, ValueError, KeyError, lzma.LZMAError) as error:
        figures, notes, problems = [], [], [f"The export could not be read ({type(error).__name__})."]
        say(FIRST, "the export could not be read")
    seconds = round(time.monotonic() - started, 1)
    failed = bool(problems)
    steps = [summary.step(FIRST, "failed" if failed else "completed", seconds=seconds,
                          reason=" ".join(problems) if failed else None, figures=figures, notes=notes)]
    steps += [summary.step(name, "not run here", reason=NEEDS_LICENCE) for name in LICENSED]
    done = "1 stage failed" if failed else "1 stage completed"
    print(f"Import run: {done}, {len(LICENSED)} need a licence and were not run here", flush=True)
    return summary.account(
        "failed" if failed else "completed", steps, closing="Import run:",
        contents=["AGRIBALYSE 3.2: ADEME's export, without the ecoinvent datasets it carried."],
        blocking=problems,
        remarks=["A full import runs on a licensed machine. Its results are not published: they hold ecoinvent data."],
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", required=True, help="where to write the run's own account (run.json)")
    args = parser.parse_args(argv)
    account = run()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    summary.write(account, Path(args.out))
    return 0 if account["status"] == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
