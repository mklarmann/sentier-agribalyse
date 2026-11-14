"""What a run says about itself: `run.json`, written by the run beside its transcript.

A page that walks through a run shows this file as it is. Every figure on the page is one the
run states here, and every sentence about a step is the run's own: the page types no number
and words no result.

    {
      "format": "sentier/run/1",
      "status": "completed",                    completed | failed
      "tag": null,                              what the run was made for, if it was a tag
      "closing": "Run ",                        how the lines begin that the run prints after
                                                its last step, if it prints any
      "steps": [
        {
          "name": "first stage",                as the run prints it: [first stage] ...
          "status": "completed",                completed | failed | not run | skipped |
                                                not run here
          "seconds": 140.1,                     or null
          "reason": null,                       why it failed, did not run or can't run here
          "figures": [{"value": 11947, "label": "datasets"}],
          "notes": ["Checksum of the archive: `cbaeed4a...`."]
        }
      ],
      "contents": ["The export as shipped, and 14 corrections."],
      "blocking": [],                           what keeps the result from being used
      "remarks": [],                            said at the end; blocks nothing
      "files": [{"name": "x.zip", "label": "for a tool", "bytes": 1, "sha256": "...", "same": true}]
    }

`not run here` is for a step that this place can't run, by a rule and not by a failure (it
needs a licence, a machine, a secret): it is no failure and the run is not incomplete for it.
`not run` is a step that did not run because an earlier one failed.

A text is plain. Two things in it are read by the page: `a name` between backquotes is shown
as code (a whole SHA-256 is shortened, with all of it in the title), and the number of a
finding the site holds becomes a link to it. Nothing else: a text is escaped.

A file read from a run is data. `shape_errors` refuses a key it does not know, a text that is
too long or holds a control character, and a list that is too long, so that nothing reaches a
page that this format does not describe.

Standard library only.
"""

import json
import re
from pathlib import Path

FORMAT = "sentier/run/1"
ENDED = ("completed", "failed")
STATUSES = ("completed", "failed", "not run", "skipped", "not run here")
NO_FAILURE = ("completed", "skipped", "not run here")
KEYS = {"format", "status", "tag", "closing", "steps", "contents", "blocking", "remarks", "files"}
STEP_KEYS = {"name", "status", "seconds", "reason", "figures", "notes"}
FILE_KEYS = {"name", "label", "bytes", "sha256", "same"}
MAX_STEPS, MAX_FIGURES, MAX_NOTES, MAX_FILES = 40, 8, 12, 40
MAX_TEXT, MAX_NAME, MAX_LABEL, MAX_VALUE = 600, 100, 60, 40
LISTS = {"contents": 12, "blocking": 40, "remarks": 12}
SHA256 = re.compile(r"[0-9a-f]{64}")


def is_text(value, limit=MAX_TEXT) -> bool:
    """A text a page can show: not empty, not too long, and without a control character."""
    return (
        isinstance(value, str)
        and 0 < len(value) <= limit
        and not any(ord(c) < 32 or ord(c) == 127 for c in value)
    )


def is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def step_errors(step, where) -> list[str]:
    if not isinstance(step, dict):
        return [f"{where} is not a step"]
    found = [f"{where} has a key this format does not know: {key}" for key in set(step) - STEP_KEYS]
    if not is_text(step.get("name"), MAX_NAME):
        found.append(f"{where}: `name` is not a short text")
    if step.get("status") not in STATUSES:
        found.append(f"{where}: `status` is not one of " + ", ".join(STATUSES))
    seconds = step.get("seconds")
    if seconds is not None and (not is_number(seconds) or seconds < 0):
        found.append(f"{where}: `seconds` is not a time")
    if step.get("reason") is not None and not is_text(step["reason"]):
        found.append(f"{where}: `reason` is not a text")
    figures = step.get("figures", [])
    if not isinstance(figures, list) or len(figures) > MAX_FIGURES:
        found.append(f"{where}: `figures` is not a list of at most {MAX_FIGURES}")
    else:
        for figure in figures:
            value = figure.get("value") if isinstance(figure, dict) else None
            if (
                not isinstance(figure, dict)
                or set(figure) != {"value", "label"}
                or not (
                    is_text(value, MAX_VALUE)
                    or (isinstance(value, int) and not isinstance(value, bool))
                )
                or not is_text(figure["label"], MAX_LABEL)
            ):
                found.append(f"{where}: a figure is not {{value, label}}")
                break
    notes = step.get("notes", [])
    if not isinstance(notes, list) or len(notes) > MAX_NOTES or not all(is_text(n) for n in notes):
        found.append(f"{where}: `notes` is not a list of at most {MAX_NOTES} texts")
    return found


def file_errors(file) -> list[str]:
    if not isinstance(file, dict) or set(file) - FILE_KEYS:
        return ["a file is not {name, label, bytes, sha256, same}"]
    found = []
    if not is_text(file.get("name"), 200) or "/" in file["name"]:
        found.append("the name of a file is not a file name")
    if not is_text(file.get("label"), MAX_LABEL):
        found.append("the label of a file is not a short text")
    size = file.get("bytes")
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        found.append("the size of a file is not a number of bytes")
    if file.get("sha256") is not None and not (
        isinstance(file["sha256"], str) and SHA256.fullmatch(file["sha256"])
    ):
        found.append("the checksum of a file is not a SHA-256")
    if file.get("same") not in (None, True, False):
        found.append("`same` of a file is not yes, no or unknown")
    return found


def shape_errors(data) -> list[str]:
    """What is wrong with a run's own account; nothing when a page can show it."""
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        return [f"not a run's own account of format {FORMAT}"]
    found = [f"a key this format does not know: {key}" for key in sorted(set(data) - KEYS)]
    if data.get("status") not in ENDED:
        found.append("`status` is not one of " + ", ".join(ENDED))
    for key, limit in (("tag", MAX_NAME), ("closing", 80)):
        if data.get(key) is not None and not is_text(data[key], limit):
            found.append(f"`{key}` is not a short text")
    steps = data.get("steps")
    if not isinstance(steps, list) or not steps or len(steps) > MAX_STEPS:
        return [*found, f"`steps` is not a list of 1 to {MAX_STEPS} steps"]
    for number, step in enumerate(steps, 1):
        found += step_errors(step, f"step {number}")
    names = [step.get("name") for step in steps if isinstance(step, dict)]
    if len(set(names)) != len(names):
        found.append("two steps have the same name")
    for key, limit in LISTS.items():
        texts = data.get(key, [])
        if not isinstance(texts, list) or len(texts) > limit or not all(is_text(t) for t in texts):
            found.append(f"`{key}` is not a list of at most {limit} texts")
    files = data.get("files", [])
    if not isinstance(files, list) or len(files) > MAX_FILES:
        found.append(f"`files` is not a list of at most {MAX_FILES} files")
    else:
        for file in files:
            errors = file_errors(file)
            if errors:
                found.append(errors[0])
                break
    return found


def step(name, status, seconds=None, reason=None, figures=(), notes=()):
    """One step, as this format writes it. A figure is (value, label)."""
    return {
        "name": name,
        "status": status,
        "seconds": seconds,
        "reason": reason,
        "figures": [{"value": value, "label": label} for value, label in figures],
        "notes": list(notes),
    }


def account(
    status, steps, *, tag=None, closing=None, contents=(), blocking=(), remarks=(), files=()
):
    """A run's own account, checked: raises ValueError for one a page could not show."""
    data = {
        "format": FORMAT,
        "status": status,
        "tag": tag,
        "closing": closing,
        "steps": list(steps),
        "contents": list(contents),
        "blocking": list(blocking),
        "remarks": list(remarks),
        "files": list(files),
    }
    errors = shape_errors(data)
    if errors:
        raise ValueError("not a run's own account: " + "; ".join(errors))
    return data


def write(data, path: Path) -> Path:
    """Write an account to `path`, checked first."""
    errors = shape_errors(data)
    if errors:
        raise ValueError("not a run's own account: " + "; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
