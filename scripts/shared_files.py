"""The files this repository shares with sentier-bafu, and the check that they are those files.

The records, the site build and the stylesheet are the same files in every Sentier dataset
repository. They are written and tested in sentier-bafu; here they are copies. What differs
between the datasets is in site/config.json and in the pages of prose, never in these files.
site/shared.json names every copied file with its checksum and the commit it was taken from.

    python3 scripts/shared_files.py check
        every file named in site/shared.json is there with the recorded checksum, and the
        shared folders hold no other file

    python3 scripts/shared_files.py take PATH --commit COMMIT
        copy the files from a checkout of sentier-bafu at PATH, as they are in COMMIT, and
        write site/shared.json

To change a shared file, change it in sentier-bafu and take it again. Standard library only.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "site/shared.json"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read_manifest(root=ROOT):
    return json.loads((Path(root) / MANIFEST).read_text(encoding="utf-8"))


def problems(root=ROOT):
    """What differs between the tree at `root` and site/shared.json, one line each."""
    root = Path(root)
    manifest = read_manifest(root)
    found = []
    for name, wanted in sorted(manifest["files"].items()):
        path = root / name
        if not path.is_file():
            found.append(f"{name}: missing")
        elif sha256(path.read_bytes()) != wanted:
            found.append(f"{name}: differs from the file of commit {manifest['commit'][:7]}")
    for folder in manifest["folders"]:
        for path in sorted((root / folder).glob("*")):
            name = path.relative_to(root).as_posix()
            if path.is_file() and name not in manifest["files"]:
                found.append(f"{name}: not a shared file, in a shared folder")
    return found


def git(source, *arguments):
    return subprocess.run(["git", "-C", str(source), *arguments], check=True, capture_output=True).stdout


def take(source, commit, root=ROOT):
    """Copy every shared file from the checkout at `source` as it is in `commit`."""
    root = Path(root)
    manifest = read_manifest(root)
    full = git(source, "rev-parse", "--verify", f"{commit}^{{commit}}").decode().strip()
    names = set(manifest["files"])
    for folder in manifest["folders"]:
        before = {name for name in names if name.startswith(folder + "/") and "/" not in name[len(folder) + 1:]}
        listed = git(source, "ls-tree", "--name-only", full, folder + "/").decode().split()
        for name in before - set(listed):
            (root / name).unlink(missing_ok=True)
        names = (names - before) | set(listed)
    files = {}
    for name in sorted(names):
        data = git(source, "show", f"{full}:{name}")
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        files[name] = sha256(data)
    manifest.update(commit=full, files=files)
    (root / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return full, len(files)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="compare the shared files with site/shared.json")
    command = sub.add_parser("take", help="copy the shared files from a checkout of sentier-bafu")
    command.add_argument("source", help="a checkout of sentier-bafu")
    command.add_argument("--commit", required=True, help="the commit to take the files from")
    args = parser.parse_args(argv)
    if args.command == "check":
        found = problems()
        for line in found:
            print(line)
        if found:
            print(f"{len(found)} shared file(s) differ. Change a shared file in sentier-bafu, then take it again.")
            return 1
        manifest = read_manifest()
        print(f"{len(manifest['files'])} shared files are those of commit {manifest['commit'][:7]}.")
        return 0
    full, count = take(args.source, args.commit)
    print(f"Took {count} files from commit {full[:7]}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
