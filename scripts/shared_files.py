"""The files the Sentier dataset repositories share, and the check that they are those files.

The records, the site build, the stylesheet, the walk through a run and the page of a
comparison are the same files in every Sentier dataset repository. They are written and
tested in one of them, the source; everywhere else they are copies. What differs between the
datasets is in each repository's own configuration and pages, never in these files.

The source says what it shares in `site/shared-sets.json`, in sets: a repository takes the
whole site, or one tool of it (the comparison of results before and after a change, say)
for a site whose frame is its own. A repository that took files records them in its own
`site/shared.json`: where they are from, the commit, the sets, and every file's checksum.

    python3 scripts/shared_files.py sets
        in the source: the sets, and the files of each

    python3 scripts/shared_files.py take PATH --commit COMMIT [--set NAME ...]
        copy the sets from a checkout of the source at PATH, as they are in COMMIT, and write
        site/shared.json. Without --set, the sets that were taken before

    python3 scripts/shared_files.py check
        every file named in site/shared.json is there with the recorded checksum, and the
        shared folders hold no other file. In the source: every file a set names exists

To change a shared file, change it in the source and take it again: then every repository
that takes the set gets the change. Standard library only.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "site/shared.json"
SETS = "site/shared-sets.json"
#: What a repository took before sets had names: the whole site.
BEFORE_SETS = ("site",)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read_manifest(root=ROOT):
    return json.loads((Path(root) / MANIFEST).read_text(encoding="utf-8"))


def expand(sets, names):
    """The files and folders of the sets `names`, with the sets each includes: (files, folders).
    Raises ValueError for a set the source does not have."""
    files, folders, seen, left = set(), set(), set(), list(names)
    while left:
        name = left.pop()
        if name in seen:
            continue
        if name not in sets:
            raise ValueError(f"the source shares no set {name!r}; it has: {', '.join(sorted(sets))}")
        seen.add(name)
        files |= set(sets[name].get("files", ()))
        folders |= set(sets[name].get("folders", ()))
        left += sets[name].get("includes", ())
    return files, folders


def in_folder(name, folder):
    """Whether a file lies directly in a folder (a shared folder is shared without its subfolders)."""
    return name.startswith(folder + "/") and "/" not in name[len(folder) + 1:]


def problems(root=ROOT):
    """What differs between the tree at `root` and its site/shared.json, one line each."""
    root = Path(root)
    manifest = read_manifest(root)
    found = []
    for name, wanted in sorted(manifest["files"].items()):
        path = root / name
        if not path.is_file():
            found.append(f"{name}: missing")
        elif sha256(path.read_bytes()) != wanted:
            found.append(f"{name}: differs from the file of commit {manifest['commit'][:7]}")
    for folder in manifest.get("folders", ()):
        for path in sorted((root / folder).glob("*")):
            name = path.relative_to(root).as_posix()
            if path.is_file() and name not in manifest["files"]:
                found.append(f"{name}: not a shared file, in a shared folder")
    return found


def source_problems(root=ROOT):
    """In the source: what a set names that is not there, one line each."""
    root = Path(root)
    sets = json.loads((root / SETS).read_text(encoding="utf-8"))["sets"]
    found = []
    for name, entry in sorted(sets.items()):
        for included in entry.get("includes", ()):
            if included not in sets:
                found.append(f"set {name}: includes {included}, which is no set")
        for file in entry.get("files", ()):
            if not (root / file).is_file():
                found.append(f"set {name}: {file} is missing")
        for folder in entry.get("folders", ()):
            if not any(p.is_file() for p in (root / folder).glob("*")):
                found.append(f"set {name}: the folder {folder} holds no file")
    return found


def git(source, *arguments):
    return subprocess.run(["git", "-C", str(source), *arguments], check=True, capture_output=True).stdout


def take(source, commit, root=ROOT, names=None):
    """Copy the files of the sets `names` from the checkout at `source` as they are in
    `commit`; without `names`, the sets this repository took before. A file that was shared
    and is no more is removed. Returns (commit, files, sets)."""
    root = Path(root)
    manifest = read_manifest(root) if (root / MANIFEST).is_file() else {"files": {}, "folders": []}
    full = git(source, "rev-parse", "--verify", f"{commit}^{{commit}}").decode().strip()
    names = sorted(names or manifest.get("sets") or BEFORE_SETS)
    try:
        sets = json.loads(git(source, "show", f"{full}:{SETS}"))["sets"]
    except subprocess.CalledProcessError:
        raise ValueError(f"commit {full[:7]} of the source has no {SETS}: it shares no sets yet") from None
    files, folders = expand(sets, names)
    for folder in sorted(folders):
        # the files of a shared folder, not what lies in a folder below it
        listed = git(source, "ls-tree", full, folder + "/").decode().splitlines()
        files |= {line.split("\t", 1)[1] for line in listed if line.split()[1] == "blob"}
    # everything is read before anything is changed: a file the source does not have at that
    # commit stops the take, and the copies here stay as they were
    try:
        contents = {name: git(source, "show", f"{full}:{name}") for name in sorted(files)}
    except subprocess.CalledProcessError:
        raise ValueError(f"commit {full[:7]} of the source lacks a file its sets name") from None
    for name in set(manifest["files"]) - files:  # shared before, and no more
        (root / name).unlink(missing_ok=True)
    taken = {}
    for name, data in contents.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        taken[name] = sha256(data)
    manifest.setdefault(
        "note",
        "The files this repository shares with the other Sentier dataset repositories. Do not edit "
        "them here: change them in the source, then run `python3 scripts/shared_files.py take`. "
        "`python3 scripts/shared_files.py check` compares.",
    )
    manifest.update(commit=full, sets=names, folders=sorted(folders), files=taken)
    (root / MANIFEST).parent.mkdir(parents=True, exist_ok=True)
    (root / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return full, len(taken), names


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("sets", help="in the source: the sets it shares")
    sub.add_parser("check", help="compare the shared files with site/shared.json")
    command = sub.add_parser("take", help="copy shared sets from a checkout of the source")
    command.add_argument("source", help="a checkout of the source repository")
    command.add_argument("--commit", required=True, help="the commit to take the files from")
    command.add_argument("--set", action="append", dest="sets", metavar="NAME", help="a set to take (repeatable)")
    args = parser.parse_args(argv)
    source = (ROOT / SETS).is_file()
    if args.command == "sets":
        if not source:
            print(f"This repository is not the source: it has no {SETS}.")
            return 1
        sets = json.loads((ROOT / SETS).read_text(encoding="utf-8"))["sets"]
        for name in sorted(sets):
            files, folders = expand(sets, [name])
            print(f"{name}: {sets[name]['about']}")
            for item in sorted(files) + [f"{folder}/ (every file in it)" for folder in sorted(folders)]:
                print(f"  {item}")
        return 0
    if args.command == "check":
        found = source_problems() if source else problems()
        for line in found:
            print(line)
        if source:
            print(f"{len(found)} problem(s) in {SETS}." if found else f"Every file that {SETS} names is here.")
            return int(bool(found))
        if found:
            print(f"{len(found)} shared file(s) differ. Change a shared file in the source, then take it again.")
            return 1
        manifest = read_manifest()
        print(f"{len(manifest['files'])} shared files are those of commit {manifest['commit'][:7]}.")
        return 0
    if source:
        print(f"This repository is the source ({SETS}): it takes its shared files from nowhere.")
        return 1
    try:
        full, count, names = take(args.source, args.commit, names=args.sets)
    except ValueError as error:
        print(f"nothing taken: {error}")
        return 1
    print(f"Took {count} files of {', '.join(names)} from commit {full[:7]}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
