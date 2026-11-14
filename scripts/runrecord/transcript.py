"""Keep what a command printed, line for line, with the time of each line.

    python3 scripts/runrecord/transcript.py --out FILE -- COMMAND [ARGUMENT ...]

Runs COMMAND and prints every line it writes, unchanged and as it comes, so a job log shows
what it always showed. Beside that it writes FILE: every line with the seconds since the
start, how the command ended, and the SHA-256 of the lines. The site shows that file line
for line (`scripts/last_run.py`, `scripts/sitebuild/lastrun.py`). No line in it is written
by anything but the command.

The file is written however the command ends: with a status other than 0, or stopped by a
signal (a job that is cancelled or runs out of time). The wrapper exits with the command's
status.

    python3 scripts/runrecord/transcript.py --keep FILE --into FOLDER

Copies a transcript into the folder of the files that may leave the machine, as
`transcript.json`, if it is one a page can show. A transcript is never edited: one that is
refused is not copied, and the status is 1. `keep` takes the words no line may hold; a
repository that has such words gives them from a script of its own.

Start it with the Python a runner has, and not through a tool that prints lines of its own
before the command starts: those lines would be in the job log and not in the file.

Standard library only.
"""

import argparse
import datetime
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

FORMAT = "sentier/transcript/1"
FORMATS = (FORMAT, "sentier-bafu/transcript/1")  # the second is what this wrapper wrote at first
MAX_LINES = 5000  # what a page can show; a run that prints more is recorded as cut
MAX_LINE = 2000


def sha256_of(lines) -> str:
    """The checksum of a transcript's lines: each line as UTF-8, with a line feed after it."""
    digest = hashlib.sha256()
    for line in lines:
        digest.update(line.encode("utf-8") + b"\n")
    return digest.hexdigest()


def record(command, out: Path, stream=None) -> int:
    """Run `command`, pass on what it prints, write the transcript to `out`. Its status."""
    stream = stream or sys.stdout
    started_at = datetime.datetime.now(datetime.UTC).replace(microsecond=0)
    started = time.perf_counter()
    lines, cut, stopped = [], False, []
    # A Python program holds its lines back when it does not write to a terminal. Without
    # this the lines of a step would arrive when the step is over, with the wrong time.
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    def stop(number, _frame):
        # Pass the signal on and keep reading: what the command still prints is recorded.
        stopped.append(signal.Signals(number).name)
        process.send_signal(number)

    previous = {number: signal.signal(number, stop) for number in (signal.SIGTERM, signal.SIGINT)}
    try:
        for raw in process.stdout:
            stream.write(raw)
            stream.flush()
            if len(lines) >= MAX_LINES:
                cut = True
                continue
            text = raw.rstrip("\r\n")
            cut = cut or len(text) > MAX_LINE
            lines.append([round(time.perf_counter() - started, 1), text[:MAX_LINE]])
        status = process.wait()
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)
        process.stdout.close()
    data = {
        "format": FORMAT,
        "command": list(command),
        "started": started_at.isoformat(),
        "seconds": round(time.perf_counter() - started, 1),
        "exit_code": status,
        "stopped_by": stopped[0] if stopped else None,
        "cut": cut,
        "lines": lines,
        "sha256": sha256_of(text for _, text in lines),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return status if status >= 0 else 128 - status


def shape_errors(data) -> list[str]:
    """What is wrong with a transcript read from a file; nothing when it can be shown."""
    if not isinstance(data, dict) or data.get("format") not in FORMATS:
        return [f"not a transcript of format {FORMAT}"]
    found = []
    lines = data.get("lines")
    if not isinstance(lines, list) or len(lines) > MAX_LINES:
        return [f"`lines` is not a list of at most {MAX_LINES} lines"]
    last = 0.0
    for number, line in enumerate(lines):
        if (
            not isinstance(line, list)
            or len(line) != 2
            or isinstance(line[0], bool)
            or not isinstance(line[0], (int, float))
            or not isinstance(line[1], str)
            or len(line[1]) > MAX_LINE
            or "\n" in line[1]
            or line[0] < last
        ):
            found.append(f"line {number + 1} is not [seconds, text] in the order of time")
            break
        last = line[0]
    if not found and data.get("sha256") != sha256_of(text for _, text in lines):
        found.append("the checksum is not the checksum of the lines")
    status = data.get("exit_code")
    if isinstance(status, bool) or not isinstance(status, int):
        found.append("`exit_code` is not a number")
    for key in ("started", "seconds", "cut"):
        if key not in data:
            found.append(f"`{key}` is missing")
    return found


def read(source: Path):
    """A transcript from a file and what is wrong with it: (data or None, problems)."""
    # Two handlers and not one: this file also runs on Python 3.12, where the formatter's
    # way of writing one handler for two kinds of error is not valid.
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except OSError:
        data = None
    except ValueError:
        data = None
    if data is None:
        return None, ["not a transcript that can be read"]
    return data, shape_errors(data)


def holding(data, words) -> list[str]:
    """The lines of a transcript that hold one of `words`, by number."""
    return [
        f"line {number + 1}"
        for number, (_, text) in enumerate(data["lines"])
        if any(word in text for word in words)
    ]


def keep(
    source: Path, into: Path, words=(), what="holds a word that must not leave the machine"
) -> list[str]:
    """Copy a transcript to `into`; return why it was not copied, if it was not."""
    data, problems = read(source)
    if not problems:
        problems = [f"{place} {what}" for place in holding(data, words)]
    if problems:
        return [f"{source.name}: {problem}" for problem in problems]
    into.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, into / "transcript.json")
    return []


def split(argv):
    """The arguments of the wrapper, and the command after `--`."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--" in argv:
        at = argv.index("--")
        return argv[:at], argv[at + 1 :]
    return argv, []


def main(argv: list[str] | None = None) -> int:
    argv, command = split(argv)
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, help="Write the transcript of COMMAND here")
    parser.add_argument("--keep", type=Path, metavar="FILE", help="A transcript to set aside")
    parser.add_argument("--into", type=Path, metavar="FOLDER", help="Where --keep copies it")
    args = parser.parse_args(argv)
    if args.out and command and not args.keep:
        return record(command, args.out)
    if args.keep and args.into and not command:
        problems = keep(args.keep, args.into)
        for problem in problems:
            print(f"not kept: {problem}")
        if not problems:
            print(f"Kept the transcript in {args.into}")
        return int(bool(problems))
    parser.error("give --out FILE -- COMMAND to record, or --keep FILE --into FOLDER to set aside")


if __name__ == "__main__":
    sys.exit(main())
