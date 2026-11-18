"""Reviewing a change: the builds that exist, what each contains, and the pairs to compare.

A reviewer does not judge a build; they judge a change: two builds that differ by one cause
or a few. This file, `review.json`, is the index of that: which builds there are, which
causes each contains, what each cause claims to move, and which pairs of builds were compared.
Each pair is a comparison of its own (`before_after.py`), with a page of its own.

    {
      "format": "sentier/review/1",
      "title": "The open contributions, one at a time",
      "runs": [
        {
          "id": "base", "label": "main, build A",
          "contains": [],                       the causes this build holds
          "reproducible": false,                whether two builds of this state agree; or null
          "replica_of": null,                   the run this one repeats, if it repeats one
          "identity": {"commit": "1e67bf0", "built": "16 November 2026"}
        }
      ],
      "causes": [
        {"id": "transport", "kind": "parameter scenario", "title": "Sea transport halved.",
         "link": null, "claim": {...}}          as in a comparison
      ],
      "pairs": [
        {"before": "base", "after": "base-transport",
         "page": "transport.html",              the page of the comparison, or null
         "classes": {"as claimed": 19, "unchanged": 46550}}     its values per class, or null
      ],
      "notes": []
    }

`isolating` answers the reviewer's question: given the causes they chose, which pair of
builds differs by exactly those? Where none does, it names the closest pair and what else
that pair contains, so that the page can say which build is missing.

A file read from a run is data: `shape_errors` refuses what the format does not describe.
Nothing here knows a dataset, a provider or a tool. Standard library only.
"""

import json
from pathlib import Path

from . import before_after
from .summary import is_text

FORMAT = "sentier/review/1"
FILE = "review.json"
KEYS = {"format", "title", "runs", "causes", "pairs", "notes"}
RUN_KEYS = {"id", "label", "contains", "reproducible", "replica_of", "identity"}
CAUSE_KEYS = {"id", "kind", "title", "link", "claim"}
PAIR_KEYS = {"before", "after", "page", "classes"}
MAX_RUNS, MAX_CAUSES, MAX_PAIRS, MAX_IDENTITY, MAX_NOTES = 40, 200, 200, 20, 12


def run_errors(run, causes) -> list[str]:
    if not isinstance(run, dict) or set(run) - RUN_KEYS:
        return ["a run has a key this format does not know"]
    where = f"run {run.get('id')!r}"
    found = []
    if not is_text(run.get("id"), 100) or not is_text(run.get("label"), 200):
        return [f"{where}: `id` and `label` are short texts"]
    contains = run.get("contains", [])
    if not isinstance(contains, list) or not set(contains) <= causes:
        found.append(f"{where}: `contains` names a cause the file does not hold")
    if run.get("reproducible") not in (None, True, False):
        found.append(f"{where}: `reproducible` is not yes, no or unknown")
    identity = run.get("identity", {})
    if (
        not isinstance(identity, dict)
        or len(identity) > MAX_IDENTITY
        or not all(is_text(k, 40) and is_text(v, 200) for k, v in identity.items())
    ):
        found.append(f"{where}: `identity` is not a short table of texts")
    return found


def shape_errors(data) -> list[str]:
    """What is wrong with an index of a review; nothing when a page can show it."""
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        return [f"not an index of a review of format {FORMAT}"]
    found = [f"a key this format does not know: {key}" for key in sorted(set(data) - KEYS)]
    if not is_text(data.get("title"), 120):
        found.append("`title` is not a short text")
    causes = data.get("causes")
    if not isinstance(causes, list) or len(causes) > MAX_CAUSES:
        return [*found, f"`causes` is not a list of at most {MAX_CAUSES}"]
    for cause in causes:
        if not isinstance(cause, dict) or set(cause) - CAUSE_KEYS:
            return [*found, "a cause has a key this format does not know"]
        # a claim of an index names no indicator: it is checked against no list of them
        found += before_after.cause_errors(cause, _Any())
    ids = [cause.get("id") for cause in causes if isinstance(cause, dict)]
    if len(set(ids)) != len(ids):
        found.append("two causes have the same id")
    runs = data.get("runs")
    if not isinstance(runs, list) or not runs or len(runs) > MAX_RUNS:
        return [*found, f"`runs` is not a list of 1 to {MAX_RUNS}"]
    for run in runs:
        found += run_errors(run, set(ids))
    run_ids = [run.get("id") for run in runs if isinstance(run, dict)]
    if len(set(run_ids)) != len(run_ids):
        found.append("two runs have the same id")
    for run in runs:
        if isinstance(run, dict) and run.get("replica_of") not in (None, *run_ids):
            found.append(f"run {run.get('id')!r}: `replica_of` is no run of the file")
    pairs = data.get("pairs", [])
    if not isinstance(pairs, list) or len(pairs) > MAX_PAIRS:
        return [*found, f"`pairs` is not a list of at most {MAX_PAIRS}"]
    for pair in pairs:
        if not isinstance(pair, dict) or set(pair) - PAIR_KEYS:
            found.append("a pair has a key this format does not know")
            break
        if pair.get("before") not in run_ids or pair.get("after") not in run_ids:
            found.append("a pair names a run the file does not hold")
            break
        page = pair.get("page")
        if page is not None and not (
            isinstance(page, str) and before_after.PAGE_NAME.fullmatch(page)
        ):
            found.append("the page of a pair is not the name of a page")
            break
        found += before_after.classes_errors(pair.get("classes"), "a pair")
    notes = data.get("notes", [])
    if not isinstance(notes, list) or len(notes) > MAX_NOTES or not all(map(is_text, notes)):
        found.append(f"`notes` is not a list of at most {MAX_NOTES} texts")
    return found


class _Any:
    """Every indicator: a claim of an index is not tied to the indicators of one comparison."""

    def __contains__(self, _):
        return True

    def __ge__(self, _):  # set(names) <= every indicator
        return True


def difference(data, pair) -> tuple[frozenset, frozenset]:
    """What the build after a pair holds that the build before does not, and the other way."""
    held = {run["id"]: frozenset(run.get("contains", ())) for run in data["runs"]}
    return held[pair["after"]] - held[pair["before"]], held[pair["before"]] - held[pair["after"]]


def isolating(data, chosen) -> dict:
    """The pair of builds that differs by exactly the causes `chosen`.

    Returns `{"pair": the pair or None, "closest": a pair or None, "also": [causes the closest
    pair differs by beside the chosen ones], "missing": [chosen causes the closest pair does
    not differ by]}`. A pair whose build before holds a cause that its build after lacks
    isolates nothing: the two are not one change apart.
    """
    chosen = frozenset(chosen)
    best, also, missing = None, [], sorted(chosen)
    for pair in data.get("pairs", ()):
        added, removed = difference(data, pair)
        if removed:
            continue
        if added == chosen:
            return {"pair": pair, "closest": pair, "also": [], "missing": []}
        if not chosen or not (added & chosen):
            continue
        extra, lacking = added - chosen, chosen - added
        if best is None or (len(lacking), len(extra)) < (len(missing), len(also)):
            best, also, missing = pair, sorted(extra), sorted(lacking)
    return {
        "pair": None,
        "closest": best,
        "also": also,
        "missing": missing if best else sorted(chosen),
    }


def run(id, label, contains=(), *, reproducible=None, replica_of=None, identity=None) -> dict:
    """One build, as this format writes it."""
    return {
        "id": id,
        "label": label,
        "contains": sorted(contains),
        "reproducible": reproducible,
        "replica_of": replica_of,
        "identity": {k: str(v) for k, v in (identity or {}).items() if v not in (None, "")},
    }


def cause(id, *, kind=None, title=None, claim=None, link=None) -> dict:
    """One cause, as the index names it: what it is and what it claims."""
    return {"id": id, "kind": kind, "title": title, "link": link, "claim": claim}


def pair(before, after, *, page=None, classes=None) -> dict:
    """One pair of builds that was compared."""
    counted = None if classes is None else {k: n for k, n in classes.items() if n}
    return {"before": before, "after": after, "page": page, "classes": counted}


def totals(comparison) -> dict:
    """The values of a comparison per class, over all its indicators."""
    found = dict.fromkeys(before_after.CLASSES, 0)
    for indicator in comparison["indicators"]:
        for kind, number in (indicator.get("classes") or {}).items():
            found[kind] += number
    return found


def index(title, runs, causes, pairs, notes=()) -> dict:
    """An index of a review, checked: raises ValueError for one a page could not show."""
    data = {
        "format": FORMAT,
        "title": title,
        "runs": list(runs),
        "causes": list(causes),
        "pairs": list(pairs),
        "notes": list(notes),
    }
    errors = shape_errors(data)
    if errors:
        raise ValueError("not an index of a review: " + "; ".join(errors))
    return data


def write(data, path: Path) -> Path:
    """Write an index to `path`, checked first."""
    errors = shape_errors(data)
    if errors:
        raise ValueError("not an index of a review: " + "; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=1, ensure_ascii=False, allow_nan=False) + "\n"
    path.write_text(text, encoding="utf-8")
    return path
