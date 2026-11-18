"""Two sets of results over the same items, compared: `before-after.json`.

A run that changes data can say what the change did to the results: it scores the same
items before and after, in the same indicators, and writes this file beside its own account
(`summary.py`). A page shows it as it is (`scripts/sitebuild/beforeafter.py`). The same file
serves any pair of results over the same items: a provider's data and a patched copy of it,
published results and a rebuild of them, two ways of building one database.

    {
      "format": "sentier/before-after/2",
      "step": "comparison",                 the step of the run this belongs to, if any
      "title": "The release and the patched copy",
      "before": {"label": "The release", "about": "As the provider ships it."},
      "after": {"label": "The patched copy", "about": null},
      "items": {"one": "dataset", "many": "datasets", "compared": 11947, "moved": 3},
      "indicator": {"one": "impact category", "many": "impact categories"},
                                            what an indicator is called here; may be left out
      "threshold": 1e-06,                   the relative difference from which a result
                                            counts as moved; null where the run sets none
      "bands": ["below 0.1", ...],          the bands `indicators[].bands` counts, or []
      "indicators": [
        {
          "id": "ef-3.1:climate-change",
          "name": "Climate change", "short": "Climate", "unit": "kg CO2 eq",
          "compared": 11947, "moved": 3, "higher": 0, "lower": 3,
          "unexplained": 0,                 moved results that no cause explains, or null
          "bands": null,                    items per band of after / before, or null
          "reason": null                    why this indicator differs as a whole, if known
        }
      ],
      "groups": {"farm": "at the farm gate"},     what an item's `group` stands for, or {}
      "causes": [
        {
          "id": "0001-a-patch", "kind": "community patch", "title": "What it corrects.",
          "rows": 3,                        rows of the data it changed, or null
          "changed": {"amount": 3},         of which, by what was changed
          "items": 3,                       items it changed
          "moved": 3                        items whose result it moved in some indicator
        }
      ],
      "rows": {"one": "exchange", "many": "exchanges",
               "compared": 420063, "differ": 188, "unexplained": 0},        or null
      "moved": [
        {
          "id": "c2d0c99c", "name": "Strawberries", "place": "ES", "group": null,
          "causes": ["0001-a-patch"],
          "values": {"ef-3.1:climate-change": [383.2, 0.659]},     [before, after]
          "note": null
        }
      ],
      "moved_not_listed": 0,                items that moved and are not in `moved`
      "notes": ["Said below the comparison."]
    }

**What a number means.** `after / before` is the ratio a page shows; 1 is no change. An item
*moved* in an indicator when its two results differ by more than `threshold`, relative to
the larger of the two. Near zero a ratio says nothing: where both results are below the
indicator's floor (`floor_of`), the item counts as not moved and its band is `near zero`.
A result of the opposite sign, or a result of zero on one side, has no ratio either: its
band is `opposite sign or zero`.

`tally` counts one indicator this way from pairs of results, so that every run that writes
this file counts alike. `BANDS` are the bands it counts.

**Version 2** adds what a review of a change needs. Every addition may be left out, and a
file of version 1 is read as before.

    "noise": {"measured": true, "between": ["build A", "build B"], "note": null},
    "reference": {"label": "Published by the provider", "about": null},
    "variant": {"id": "strict", "label": "Strict"},           this file is one of several
    "variants": [{"id": "strict", "label": "Strict", "page": "strict.html"}, ...],
    indicators[]:  "noise": 0.21,                      what two builds of one state differ by
                   "classes": {"as claimed": 19, ...},  values per class (below)
                   "closer": 4, "further": 1            moved towards the reference, or away
    causes[]:      "link": "https://...",
                   "claim": {
                     "text": "Only product 26181 moves, downwards, by less than 2.5 %.",
                     "derived": false,                 true: the scope is a computed reach
                     "reach": 1,                       items the claim covers, or null
                     "scope": [{"indicators": "*", "items": ["26181"],
                                "direction": "down", "largest": 0.025}]
                   }
    indicators[]:  "floor": 0.02                       results below it counted as near zero
    moved[]:       "moved": ["x:climate"],            the indicators in which it moved
                   "classes": {"x:climate": "as claimed"},
                   "reference": {"x:climate": 0.61},
                   "detail": "p-1.json"                 its breakdown, loaded when it is opened

**A claim** says what a cause is expected to move: which indicators and items, in which
direction, and by how much at most, relative to the result before. An empty scope says that
nothing moves. `derived` marks a scope that was computed (every item whose supply chain
reaches the change) instead of stated by an author: such a claim cannot be under-declared,
and it expects no item to move. A repository that may not publish the list of items keeps it
to itself, classifies with it, and writes only `reach`, the number of items.

**The classes** put each value (an item in an indicator) into one of six, with `classify`:

    unchanged             the two results agree within the threshold
    within noise          they differ by no more than two builds of one state do
    as claimed            moved, inside a claim, in its direction and within its size
    off claim             moved, inside a claim, in another direction or further
    not claimed           moved, and no claim covers it
    claimed, not moved    a stated claim covers it, and it did not move

Noise is measured, per indicator, as the largest relative difference between two builds of
the same state; where no such pair exists, nothing is within noise, and the file says that
noise was not measured. The reference is a third set of results (a provider's published
ones): the page says whether a moved value came closer to it or went further, and never that
one is better.

`sentier/before-after-detail/1` is the breakdown of one item, a file of its own
(`detail_errors`): per indicator, the parts its result is made of, before and after.

A file read from a run is data. `shape_errors` refuses a key it does not know, a text that
is too long or holds a control character, a number that is not finite and a list that is too
long. `moved` holds results of single items: a run lists as many as it may show, and says
how many it left out.

Nothing here knows a dataset, a provider or a tool. Standard library only.
"""

import json
import math
import re
from pathlib import Path

from .summary import is_number, is_text

FORMATS = ("sentier/before-after/1", "sentier/before-after/2")
FORMAT = FORMATS[-1]
DETAIL_FORMAT = "sentier/before-after-detail/1"
FILE = "before-after.json"
KEYS = {
    "format", "step", "title", "before", "after", "items", "indicator", "threshold", "bands",
    "indicators", "groups", "causes", "rows", "moved", "moved_not_listed", "notes",
}  # fmt: skip
SIDE_KEYS = {"label", "about"}
ITEMS_KEYS = {"one", "many", "compared", "moved"}
INDICATOR_KEYS = {
    "id", "name", "short", "unit", "compared", "moved", "higher", "lower", "unexplained",
    "bands", "reason",
}  # fmt: skip
CAUSE_KEYS = {"id", "kind", "title", "rows", "changed", "items", "moved"}
ROWS_KEYS = {"one", "many", "compared", "differ", "unexplained"}
MOVED_KEYS = {"id", "name", "place", "group", "causes", "values", "note"}
# what version 2 adds, per part of the file
ADDED = {
    "file": {"noise", "reference", "variant", "variants"},
    "indicator": {"noise", "floor", "classes", "closer", "further"},
    "cause": {"claim", "link"},
    "moved": {"moved", "classes", "reference", "detail"},
}
CLAIM_KEYS = {"text", "derived", "reach", "scope"}
SCOPE_KEYS = {"indicators", "items", "direction", "largest"}
DIRECTIONS = ("up", "down", "any")
UNCHANGED, NOISE, AS_CLAIMED = "unchanged", "within noise", "as claimed"
OFF_CLAIM, NOT_CLAIMED, NOT_MOVED = "off claim", "not claimed", "claimed, not moved"
#: The six classes of a value, in the order a page lists them.
CLASSES = (UNCHANGED, NOISE, AS_CLAIMED, OFF_CLAIM, NOT_CLAIMED, NOT_MOVED)
MAX_SCOPE, MAX_SCOPE_ITEMS, MAX_VARIANTS, MAX_PARTS = 50, 500, 10, 200
PAGE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}\.html")
FILE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}\.json")
MAX_INDICATORS, MAX_CAUSES, MAX_GROUPS, MAX_BANDS, MAX_NOTES = 60, 200, 20, 20, 12
MAX_MOVED = 5000
#: The largest file a run may write. A site reads no larger file of a run, and a page holds
#: the whole file: a comparison with more to say lists fewer items and says how many it left out.
MAX_BYTES = 12 * 1024 * 1024
MAX_ID, MAX_NAME, MAX_WORD, MAX_TEXT = 100, 300, 40, 600

#: The bands of `after / before`, from far below 1 to far above it: the same distance from
#: 1 on both sides. Then what has no ratio.
EDGES = (0.1, 0.5, 0.8, 1 / 1.1, 1.1, 1.25, 2.0, 10.0)
BANDS = (
    "below 0.1",
    "0.1 to 0.5",
    "0.5 to 0.8",
    "0.8 to 0.91",
    "0.91 to 1.1",
    "1.1 to 1.25",
    "1.25 to 2",
    "2 to 10",
    "above 10",
    "near zero",
    "opposite sign or zero",
)
MIDDLE, NEAR_ZERO, OPPOSITE = "0.91 to 1.1", "near zero", "opposite sign or zero"
#: A result below this share of the median size of the results before is near zero.
FLOOR_FACTOR = 0.01


# ------------------------------------------------------------------------ counting alike


def ratio(before, after):
    """`after / before`, or None where that says nothing: a zero or another sign on one side.

    >>> ratio(2.0, 3.0), ratio(0.0, 3.0), ratio(2.0, -1.0), ratio(-2.0, -1.0), ratio(None, 1)
    (1.5, None, None, 0.5, None)
    """
    if before is None or after is None or before == 0 or after == 0:
        return None
    if (before > 0) != (after > 0):
        return None
    found = after / before
    # two results too far apart for a quotient (it would be 0 or infinite) have none
    return found if math.isfinite(found) and found != 0 else None


def floor_of(values, factor=FLOOR_FACTOR) -> float:
    """The size below which a result of an indicator is near zero: `factor` times the median
    size of the results that are not zero. Without such a result there is no floor.

    >>> floor_of([0.0, 1.0, -3.0, 2.0]), floor_of([0.0, None])
    (0.02, 0.0)
    """
    sizes = sorted(abs(v) for v in values if v is not None and math.isfinite(v) and v != 0)
    if not sizes:
        return 0.0
    middle = len(sizes) // 2
    median = sizes[middle] if len(sizes) % 2 else (sizes[middle - 1] + sizes[middle]) / 2
    return factor * median


def band(before, after, floor=0.0) -> str | None:
    """The band of one pair of results; None where a side is missing.

    >>> band(1.0, 1.05), band(1.0, 0.05), band(1.0, 12.0), band(1.0, -1.0), band(0.0, 0.0)
    ('0.91 to 1.1', 'below 0.1', 'above 10', 'opposite sign or zero', 'near zero')
    >>> band(1e-9, 5e-9, floor=1e-6), band(None, 1.0)
    ('near zero', None)
    """
    if before is None or after is None:
        return None
    if abs(before) <= floor and abs(after) <= floor:
        return NEAR_ZERO
    found = ratio(before, after)
    if found is None:
        return OPPOSITE
    for edge, name in zip(EDGES, BANDS, strict=False):
        if found < edge:
            return name
    return BANDS[len(EDGES)]


def moved(before, after, threshold, floor=0.0) -> bool:
    """Whether two results differ by more than `threshold`, relative to the larger of the
    two; never where both are near zero.

    >>> moved(1.0, 1.0000001, 1e-6), moved(1.0, 1.1, 1e-6), moved(0.0, 0.0, 1e-6)
    (False, True, False)
    >>> moved(1e-9, 5e-9, 1e-6, floor=1e-6)
    False
    """
    if before is None or after is None:
        return False
    if abs(before) <= floor and abs(after) <= floor:
        return False
    size = max(abs(before), abs(after))
    return size > 0 and abs(after - before) / size > threshold


def tally(pairs, threshold, floor=None, bands=False) -> dict:
    """One indicator counted from its pairs `(before, after)`: how many were compared, moved,
    went up and went down, and with `bands` how many lie in each band. A pair with a side
    missing is not compared. `floor` None takes the floor from the results before.

    >>> tally([(1.0, 1.0), (1.0, 2.0), (2.0, 1.0), (None, 1.0)], 1e-6)
    {'compared': 3, 'moved': 2, 'higher': 1, 'lower': 1, 'bands': None}
    """
    pairs = [(b, a) for b, a in pairs if b is not None and a is not None]
    if floor is None:
        floor = floor_of(b for b, _ in pairs)
    counts = dict.fromkeys(BANDS, 0)
    found = {"compared": len(pairs), "moved": 0, "higher": 0, "lower": 0}
    for before, after in pairs:
        counts[band(before, after, floor)] += 1
        if moved(before, after, threshold, floor):
            found["moved"] += 1
            found["higher" if after > before else "lower"] += 1
    return found | {"bands": [counts[name] for name in BANDS] if bands else None}


# ------------------------------------------------------------------------ claims and classes


def difference(before, after) -> float:
    """How far two results lie apart, relative to the larger of the two; 0 where both are 0.

    >>> difference(2.0, 1.0), difference(0.0, 0.0), difference(1.0, -1.0)
    (0.5, 0.0, 2.0)
    """
    size = max(abs(before), abs(after))
    return abs(after - before) / size if size else 0.0


def change(before, after):
    """The change relative to the result before, as a reader says it ("2.5 % less"); None
    where the result before is zero.

    >>> change(2.0, 1.0), change(4.0, 6.0), change(0.0, 1.0)
    (-0.5, 0.5, None)
    """
    return (after - before) / abs(before) if before else None


def scope(indicators="*", items="*", direction="any", largest=None) -> dict:
    """One entry of a claim's scope: these indicators and items may move, in this direction,
    by `largest` at most relative to the result before. `"*"` is all of them."""
    return {
        "indicators": indicators if indicators == "*" else sorted(indicators),
        "items": items if items == "*" else sorted(items),
        "direction": direction,
        "largest": largest,
    }


def claim(text, entries=(), *, derived=False, reach=None) -> dict:
    """What a cause is expected to move. Without an entry: nothing."""
    return {"text": text, "derived": derived, "reach": reach, "scope": list(entries)}


def covers(entry, item, indicator) -> bool:
    """Whether a scope entry covers one item in one indicator. `items` may be any set of ids,
    so that a repository classifies with a list it does not publish."""
    return (entry["indicators"] == "*" or indicator in entry["indicators"]) and (
        entry["items"] == "*" or item in entry["items"]
    )


def fits(entry, before, after) -> bool:
    """Whether a move is the one a scope entry expects: its direction, and within its size."""
    if entry["direction"] != "any" and (entry["direction"] == "up") != (after > before):
        return False
    if entry.get("largest") is None:
        return True
    moved_by = change(before, after)
    return moved_by is not None and abs(moved_by) <= entry["largest"]


def classify(before, after, threshold, noise=None, covering=(), floor=0.0):
    """The class of one value; None where a side is missing.

    `covering` is the claims' scope entries that cover this item in this indicator, each as
    `(entry, derived)`. `noise` is what two builds of one state differ by in this indicator.

    >>> classify(1.0, 1.0, 1e-6), classify(1.0, 1.1, 1e-6), classify(1.0, 1.1, 1e-6, noise=0.2)
    ('unchanged', 'not claimed', 'within noise')
    >>> down = (scope(direction="down", largest=0.25), False)
    >>> classify(4.0, 3.5, 1e-6, covering=[down]), classify(4.0, 2.0, 1e-6, covering=[down])
    ('as claimed', 'off claim')
    >>> classify(4.0, 4.0, 1e-6, covering=[down])
    'claimed, not moved'
    >>> classify(4.0, 4.0, 1e-6, covering=[(down[0], True)])
    'unchanged'
    """
    if before is None or after is None:
        return None
    if not moved(before, after, threshold, floor):
        # a computed reach expects nothing to move: only a stated claim can be unmet
        return NOT_MOVED if any(not derived for _, derived in covering) else UNCHANGED
    if noise and difference(before, after) <= noise:
        return NOISE
    if not covering:
        return NOT_CLAIMED
    return AS_CLAIMED if any(fits(entry, before, after) for entry, _ in covering) else OFF_CLAIM


def classes_of(values, threshold, *, noise=None, claims=(), floors=None) -> dict:
    """A whole pair, classified: `{"classes": {indicator: {item: class}}, "counts":
    {indicator: {class: number}}}`.

    `values` is `{indicator id: {item id: (before, after)}}`, `noise` and `floors` are numbers
    per indicator id, and `claims` are claims as `claim()` writes them; an entry's `items` may
    be a set this repository keeps to itself.

    >>> found = classes_of({"x": {"a": (1.0, 1.0), "b": (2.0, 1.0)}}, 1e-6,
    ...                    claims=[claim("b halves", [scope(items={"b"}, direction="down")])])
    >>> found["classes"]["x"], found["counts"]["x"]["as claimed"], found["counts"]["x"]["unchanged"]
    ({'a': 'unchanged', 'b': 'as claimed'}, 1, 1)
    """
    entries = [(entry, bool(one.get("derived"))) for one in claims for entry in one["scope"]]
    classes, counts = {}, {}
    for indicator, pairs in values.items():
        here = [e for e in entries if e[0]["indicators"] == "*" or indicator in e[0]["indicators"]]
        level = (noise or {}).get(indicator)
        floor = (floors or {}).get(indicator, 0.0)
        found, counted = {}, dict.fromkeys(CLASSES, 0)
        for item, (before, after) in pairs.items():
            covering = [e for e in here if e[0]["items"] == "*" or item in e[0]["items"]]
            kind = classify(before, after, threshold, level, covering, floor)
            if kind is not None:
                found[item] = kind
                counted[kind] += 1
        classes[indicator], counts[indicator] = found, counted
    return {"classes": classes, "counts": counts}


def noise_of(first, second) -> float:
    """What two builds of one state differ by, in one indicator: the largest relative
    difference over the items both hold. `first` and `second` are `{item id: result}`.

    >>> noise_of({"a": 1.0, "b": 2.0, "c": 5.0}, {"a": 1.0, "b": 2.5})
    0.2
    """
    shared = [k for k in first if k in second and first[k] is not None and second[k] is not None]
    return max((difference(first[k], second[k]) for k in shared), default=0.0)


def towards(before, after, reference):
    """Whether a result came closer to a reference or went further: "closer", "further", or
    None where it is as far as before or a value is missing. Closer is not better.

    >>> towards(4.0, 3.0, 2.0), towards(4.0, 5.0, 2.0), towards(1.0, 3.0, 2.0), towards(1, 2, None)
    ('closer', 'further', None, None)
    """
    if before is None or after is None or reference is None:
        return None
    was, now = abs(before - reference), abs(after - reference)
    return "closer" if now < was else "further" if now > was else None


# ------------------------------------------------------------------------ the shape


def is_count(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def is_result(value) -> bool:
    """None, or a number a page can show: finite, and not too large to be one at all."""
    if value is None:
        return True
    try:
        return is_number(value) and math.isfinite(value) and abs(value) < 1e300
    except OverflowError:
        return False


def is_id(value, limit=None) -> bool:
    """A text that names something: it can be looked up, so it is a text before anything else."""
    return isinstance(value, str) and is_text(value, limit or MAX_ID)


def _optional(value, limit) -> bool:
    return value is None or is_text(value, limit)


def side_errors(side, where) -> list[str]:
    if not isinstance(side, dict) or set(side) - SIDE_KEYS:
        return [f"`{where}` is not {{label, about}}"]
    if not is_text(side.get("label"), 60) or not _optional(side.get("about"), MAX_NAME):
        return [f"`{where}` has no short label, or its `about` is not a text"]
    return []


def _share(value) -> bool:
    return value is None or (is_result(value) and not isinstance(value, bool) and value >= 0)


def claim_errors(found_claim, where, indicators) -> list[str]:
    if not isinstance(found_claim, dict) or set(found_claim) != CLAIM_KEYS:
        return [f"{where}: `claim` is not {{text, derived, reach, scope}}"]
    found = []
    if not is_text(found_claim["text"], MAX_TEXT) or not isinstance(found_claim["derived"], bool):
        found.append(f"{where}: a claim has a text, and says whether it was derived")
    if found_claim["reach"] is not None and not is_count(found_claim["reach"]):
        found.append(f"{where}: the reach of a claim is not a count")
    entries = found_claim["scope"]
    if not isinstance(entries, list) or len(entries) > MAX_SCOPE:
        return [*found, f"{where}: the scope of a claim is not a list of at most {MAX_SCOPE}"]
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != SCOPE_KEYS:
            return [
                *found,
                f"{where}: a scope entry is not {{indicators, items, direction, largest}}",
            ]
        named, items = entry["indicators"], entry["items"]
        if named != "*" and not (isinstance(named, list) and set(named) <= indicators):
            found.append(f"{where}: a scope names an indicator the file does not hold")
        if items != "*" and not (
            isinstance(items, list)
            and len(items) <= MAX_SCOPE_ITEMS
            and all(is_text(i, MAX_ID) for i in items)
        ):
            found.append(f"{where}: the items of a scope are not at most {MAX_SCOPE_ITEMS} ids")
        if entry["direction"] not in DIRECTIONS or not _share(entry["largest"]):
            found.append(f"{where}: a scope has a direction (up, down, any) and a largest move")
    return found


def classes_errors(counted, where) -> list[str]:
    if counted is None:
        return []
    if not isinstance(counted, dict) or set(counted) - set(CLASSES):
        return [f"{where}: `classes` names a class this format does not know"]
    if not all(is_count(n) for n in counted.values()):
        return [f"{where}: `classes` is not a table of counts"]
    return []


def indicator_errors(indicator, bands, version=2) -> list[str]:
    allowed = INDICATOR_KEYS | (ADDED["indicator"] if version > 1 else set())
    if not isinstance(indicator, dict) or set(indicator) - allowed:
        return ["an indicator has a key this format does not know"]
    where = f"indicator {indicator.get('id')!r}"
    found = []
    if not is_id(indicator.get("id")) or not is_text(indicator.get("name"), MAX_ID):
        return ["an indicator has no `id` or no `name` that is a short text"]
    for key in ("short", "unit"):
        if not _optional(indicator.get(key), MAX_WORD):
            found.append(f"{where}: `{key}` is not a short text")
    for key in ("compared", "moved", "higher", "lower"):
        if not is_count(indicator.get(key)):
            found.append(f"{where}: `{key}` is not a count")
    if indicator.get("unexplained") is not None and not is_count(indicator["unexplained"]):
        found.append(f"{where}: `unexplained` is not a count")
    counted = indicator.get("bands")
    if counted is not None and not (
        isinstance(counted, list) and len(counted) == len(bands) and all(map(is_count, counted))
    ):
        found.append(f"{where}: `bands` is not one count for each band")
    if not _optional(indicator.get("reason"), MAX_TEXT):
        found.append(f"{where}: `reason` is not a text")
    if not found and (
        indicator["moved"] > indicator["compared"]
        or indicator["higher"] + indicator["lower"] > indicator["moved"]
    ):
        found.append(f"{where}: more moved than were compared, or more went up and down than moved")
    for key in ("noise", "floor"):
        if not _share(indicator.get(key)):
            found.append(f"{where}: `{key}` is not a size")
    found += classes_errors(indicator.get("classes"), where)
    for key in ("closer", "further"):
        if indicator.get(key) is not None and not is_count(indicator[key]):
            found.append(f"{where}: `{key}` is not a count")
    return found


def cause_errors(cause, indicators=frozenset(), version=2) -> list[str]:
    allowed = CAUSE_KEYS | (ADDED["cause"] if version > 1 else set())
    if not isinstance(cause, dict) or set(cause) - allowed:
        return ["a cause has a key this format does not know"]
    where = f"cause {cause.get('id')!r}"
    found = []
    if not is_id(cause.get("id")):
        return ["a cause has no `id` that is a short text"]
    if not _optional(cause.get("kind"), MAX_WORD) or not _optional(cause.get("title"), MAX_NAME):
        found.append(f"{where}: `kind` or `title` is not a text")
    for key in ("rows", "items", "moved"):
        if cause.get(key) is not None and not is_count(cause[key]):
            found.append(f"{where}: `{key}` is not a count")
    changed = cause.get("changed", {})
    if (
        not isinstance(changed, dict)
        or len(changed) > 12
        or not all(is_text(k, MAX_WORD) and is_count(v) for k, v in changed.items())
    ):
        found.append(f"{where}: `changed` is not a short table of counts")
    if cause.get("claim") is not None:
        found += claim_errors(cause["claim"], where, indicators)
    link = cause.get("link")
    if link is not None and not (is_text(link, 500) and link.startswith("https://")):
        found.append(f"{where}: `link` is not an https address")
    return found


def moved_errors(item, indicators, causes, groups, version=2) -> list[str]:
    allowed = MOVED_KEYS | (ADDED["moved"] if version > 1 else set())
    if not isinstance(item, dict) or set(item) - allowed:
        return ["an item has a key this format does not know"]
    where = f"item {item.get('id')!r}"
    if not is_id(item.get("id")) or not is_text(item.get("name"), MAX_NAME):
        return ["an item has no `id` or no `name` that is a text"]
    found = []
    if not _optional(item.get("place"), 60) or not _optional(item.get("note"), MAX_TEXT):
        found.append(f"{where}: `place` or `note` is not a text")
    if item.get("group") is not None and not (
        isinstance(item["group"], str) and item["group"] in groups
    ):
        found.append(f"{where}: `group` is not one of `groups`")
    named = item.get("causes", [])
    if not isinstance(named, list) or not all(isinstance(c, str) and c in causes for c in named):
        found.append(f"{where}: `causes` names a cause the file does not hold")
    values = item.get("values")
    if not isinstance(values, dict) or not values:
        return [*found, f"{where}: `values` holds no result"]
    for key, pair in values.items():
        if key not in indicators:
            found.append(f"{where}: a result of an indicator the file does not hold")
            break
        if not (
            isinstance(pair, list)
            and len(pair) == 2
            and all(is_result(v) and not isinstance(v, bool) for v in pair)
        ):
            found.append(f"{where}: a result is not [before, after]")
            break
    flagged = item.get("moved")
    if flagged is not None and not (
        isinstance(flagged, list)
        and all(isinstance(key, str) for key in flagged)
        and set(flagged) <= set(values)
    ):
        found.append(f"{where}: `moved` names an indicator the item has no result in")
    kinds = item.get("classes")
    if kinds is not None and not (
        isinstance(kinds, dict)
        and set(kinds) <= indicators
        and all(isinstance(kind, str) and kind in CLASSES for kind in kinds.values())
    ):
        found.append(f"{where}: `classes` is not a class for each of its indicators")
    against = item.get("reference")
    if against is not None and not (
        isinstance(against, dict)
        and set(against) <= indicators
        and all(is_result(value) and not isinstance(value, bool) for value in against.values())
    ):
        found.append(f"{where}: `reference` is not a result for each of its indicators")
    detail = item.get("detail")
    if detail is not None and not (isinstance(detail, str) and FILE_NAME.fullmatch(detail)):
        found.append(f"{where}: `detail` is not the name of a JSON file")
    return found


def file_errors(data) -> list[str]:
    """What version 2 adds at the top of a file: noise, the reference, the variants."""
    found = []
    noise = data.get("noise")
    if noise is not None and not (
        isinstance(noise, dict)
        and set(noise) == {"measured", "between", "note"}
        and isinstance(noise["measured"], bool)
        and (
            noise["between"] is None
            or (
                isinstance(noise["between"], list)
                and len(noise["between"]) == 2
                and all(is_text(name, MAX_ID) for name in noise["between"])
            )
        )
        and _optional(noise["note"], MAX_TEXT)
    ):
        found.append("`noise` is not {measured, between, note}")
    if data.get("reference") is not None:
        found += side_errors(data["reference"], "reference")
    variants = data.get("variants", [])
    if not isinstance(variants, list) or len(variants) > MAX_VARIANTS:
        return [*found, f"`variants` is not a list of at most {MAX_VARIANTS}"]
    for one in variants:
        if not (
            isinstance(one, dict)
            and set(one) == {"id", "label", "page"}
            and is_text(one["id"], MAX_WORD)
            and is_text(one["label"], 60)
            and isinstance(one["page"], str)
            and PAGE_NAME.fullmatch(one["page"])
        ):
            found.append("a variant is not {id, label, page}, the page a file name")
            break
    variant = data.get("variant")
    if variant is not None and not (
        isinstance(variant, dict)
        and set(variant) == {"id", "label"}
        and is_text(variant["id"], MAX_WORD)
        and is_text(variant["label"], 60)
    ):
        found.append("`variant` is not {id, label}")
    return found


def shape_errors(data) -> list[str]:
    """What is wrong with a comparison; nothing when a page can show it. A file of an earlier
    version is checked as that version: it holds nothing a later one added."""
    if not isinstance(data, dict) or data.get("format") not in FORMATS:
        return [f"not a comparison of format {FORMAT}"]
    version = FORMATS.index(data["format"]) + 1
    allowed = KEYS | (ADDED["file"] if version > 1 else set())
    found = [f"a key this format does not know: {key}" for key in sorted(set(data) - allowed)]
    found += file_errors(data)
    if not is_text(data.get("title"), 120):
        found.append("`title` is not a short text")
    if not _optional(data.get("step"), MAX_ID):
        found.append("`step` is not the name of a step")
    for where in ("before", "after"):
        found += side_errors(data.get(where), where)
    items = data.get("items")
    if (
        not isinstance(items, dict)
        or set(items) != ITEMS_KEYS
        or not all(is_text(items[key], 30) for key in ("one", "many"))
        or not all(is_count(items[key]) for key in ("compared", "moved"))
    ):
        found.append("`items` is not {one, many, compared, moved}")
    word = data.get("indicator")
    if word is not None and not (
        isinstance(word, dict)
        and set(word) == {"one", "many"}
        and all(is_text(w, 30) for w in word.values())
    ):
        found.append("`indicator` is not {one, many}")
    threshold = data.get("threshold")
    if threshold is not None and not (is_result(threshold) and threshold >= 0):
        found.append("`threshold` is not a share")
    bands = data.get("bands", [])
    if (
        not isinstance(bands, list)
        or len(bands) > MAX_BANDS
        or not all(is_text(name, MAX_WORD) for name in bands)
    ):
        return [*found, f"`bands` is not a list of at most {MAX_BANDS} names"]
    indicators = data.get("indicators")
    if not isinstance(indicators, list) or not indicators or len(indicators) > MAX_INDICATORS:
        return [*found, f"`indicators` is not a list of 1 to {MAX_INDICATORS}"]
    for indicator in indicators:
        found += indicator_errors(indicator, bands, version)
    ids = [i["id"] for i in indicators if isinstance(i, dict) and is_id(i.get("id"))]
    if len(ids) != len(indicators):
        return found  # an indicator without an id was said above
    if len(set(ids)) != len(ids):
        found.append("two indicators have the same id")
    groups = data.get("groups", {})
    if (
        not isinstance(groups, dict)
        or len(groups) > MAX_GROUPS
        or not all(is_id(k, MAX_WORD) and is_text(v, MAX_ID) for k, v in groups.items())
    ):
        found.append("`groups` is not a short table of names")
        groups = {}
    causes = data.get("causes", [])
    if not isinstance(causes, list) or len(causes) > MAX_CAUSES:
        return [*found, f"`causes` is not a list of at most {MAX_CAUSES}"]
    for cause in causes:
        found += cause_errors(cause, set(ids), version)
    cause_ids = [c["id"] for c in causes if isinstance(c, dict) and is_id(c.get("id"))]
    if len(cause_ids) != len(causes):
        return found
    if len(set(cause_ids)) != len(cause_ids):
        found.append("two causes have the same id")
    rows = data.get("rows")
    if rows is not None and (
        not isinstance(rows, dict)
        or set(rows) != ROWS_KEYS
        or not all(is_text(rows[key], 30) for key in ("one", "many"))
        or not all(is_count(rows[key]) for key in ("compared", "differ", "unexplained"))
    ):
        found.append("`rows` is not {one, many, compared, differ, unexplained}")
    listed = data.get("moved", [])
    if not isinstance(listed, list) or len(listed) > MAX_MOVED:
        return [*found, f"`moved` is not a list of at most {MAX_MOVED} items"]
    seen = set()
    for item in listed:
        errors = moved_errors(item, set(ids), set(cause_ids), groups, version)
        if not errors and item["id"] in seen:
            errors = [f"two items have the id {item['id']!r}"]
        if errors:
            found.append(errors[0])
            break
        seen.add(item["id"])
    if not is_count(data.get("moved_not_listed", 0)):
        found.append("`moved_not_listed` is not a count")
    notes = data.get("notes", [])
    if not isinstance(notes, list) or len(notes) > MAX_NOTES or not all(map(is_text, notes)):
        found.append(f"`notes` is not a list of at most {MAX_NOTES} texts")
    return found


# ------------------------------------------------------------------------ writing one


def indicator(
    id, name, counts, *, short=None, unit=None, unexplained=None, reason=None,
    noise=None, floor=None, classes=None, closer=None, further=None,
):  # fmt: skip
    """One indicator, as this format writes it; `counts` is what `tally` returned, `classes`
    the counts of this indicator from `classes_of`, `floor` the size below which a result
    of it counted as near zero."""
    return {
        "id": id,
        "name": name,
        "short": short,
        "unit": unit,
        **{key: counts[key] for key in ("compared", "moved", "higher", "lower")},
        "unexplained": unexplained,
        "bands": counts.get("bands"),
        "reason": reason,
        "noise": noise,
        "floor": floor or None,
        "classes": None if classes is None else {k: n for k, n in classes.items() if n},
        "closer": closer,
        "further": further,
    }


def cause(
    id, *, kind=None, title=None, rows=None, changed=None, items=None, moved=None,
    claim=None, link=None,
):  # fmt: skip
    """One cause of a difference: a step, a patch, a decision. `claim` is what it is expected
    to move (`claim()`); a scope of a claim that goes into a file holds lists, never a set a
    repository keeps to itself: `published(claim)` leaves such a list out."""
    return {
        "id": id,
        "kind": kind,
        "title": title,
        "rows": rows,
        "changed": dict(changed or {}),
        "items": items,
        "moved": moved,
        "claim": claim,
        "link": link,
    }


def published(found_claim, keep_items=True):
    """A claim as a file holds it. With `keep_items` false, or where a scope lists more items
    than a file may, the items are left out and the claim says only how many it reaches: the
    scope of such a claim is empty in the file, and it is marked as derived so that a reader
    does not take the empty scope for "nothing moves"."""
    reach = found_claim.get("reach")
    listed = [e["items"] for e in found_claim["scope"] if e["items"] != "*"]
    if reach is None and listed and len(listed) == len(found_claim["scope"]):
        reach = len(set().union(*listed))
    fits_a_file = all(len(items) <= MAX_SCOPE_ITEMS for items in listed)
    if keep_items and fits_a_file and len(found_claim["scope"]) <= MAX_SCOPE:
        entries = [scope(e["indicators"], e["items"], e["direction"], e["largest"])
                   for e in found_claim["scope"]]  # fmt: skip
        return claim(found_claim["text"], entries, derived=found_claim["derived"], reach=reach)
    return claim(found_claim["text"], (), derived=True, reach=reach)


def item(
    id, name, values, *, place=None, group=None, causes=(), note=None,
    moved=None, classes=None, reference=None, detail=None,
):  # fmt: skip
    """One item that moved, with its results `{indicator id: (before, after)}`. `moved` names
    the indicators in which it moved, as the run counted it: results are written with fewer
    digits than they were compared with, so a page must not work that out again."""
    return {
        "id": id,
        "name": name,
        "place": place,
        "group": group,
        "causes": list(causes),
        "values": {key: [pair[0], pair[1]] for key, pair in values.items()},
        "note": note,
        "moved": None if moved is None else sorted(moved),
        "classes": None if classes is None else dict(classes),
        "reference": None if reference is None else dict(reference),
        "detail": detail,
    }


def account(title, before, after, items, indicators, **more):
    """A comparison, checked: raises ValueError for one a page could not show. `before` and
    `after` are `(label, about)`, `items` is `(one, many, compared, moved)`."""
    data = {
        "format": FORMAT,
        "step": more.pop("step", None),
        "title": title,
        "before": {"label": before[0], "about": before[1]},
        "after": {"label": after[0], "about": after[1]},
        "items": dict(zip(("one", "many", "compared", "moved"), items, strict=True)),
        "indicator": more.pop("indicator", None),
        "threshold": more.pop("threshold", None),
        "bands": list(more.pop("bands", ())),
        "indicators": list(indicators),
        "groups": dict(more.pop("groups", {})),
        "causes": list(more.pop("causes", ())),
        "rows": more.pop("rows", None),
        "moved": list(more.pop("moved", ())),
        "moved_not_listed": more.pop("moved_not_listed", 0),
        "notes": list(more.pop("notes", ())),
        "noise": more.pop("noise", None),
        "reference": more.pop("reference", None),
        "variant": more.pop("variant", None),
        "variants": list(more.pop("variants", ())),
    }
    if more:
        raise ValueError(f"a comparison has no {sorted(more)}")
    errors = shape_errors(data)
    if errors:
        raise ValueError("not a comparison: " + "; ".join(errors))
    return data


def write(data, path: Path) -> Path:
    """Write a comparison to `path`, checked first."""
    errors = shape_errors(data)
    if errors:
        raise ValueError("not a comparison: " + "; ".join(errors))
    # one line per listed item: a file of many items is half the size it would be indented
    listed = data.get("moved") or []
    head = json.dumps(data | {"moved": []}, indent=1, ensure_ascii=False, allow_nan=False)
    if listed:
        rows = ",\n".join("  " + json.dumps(i, ensure_ascii=False, allow_nan=False) for i in listed)
        opening, closing = head.rsplit('"moved": []', 1)
        head = f'{opening}"moved": [\n{rows}\n ]{closing}'
    text = head + "\n"
    size = len(text.encode("utf-8"))
    if size > MAX_BYTES:
        raise ValueError(
            f"not a comparison a site reads: the file would be {size} bytes, and a site reads "
            f"{MAX_BYTES} at most. List fewer items (`listed`)."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ------------------------------------------------------------------------ a whole pair


def distance(pair) -> float:
    """How far a pair of results lies from no change: the size of log10(after / before); a
    result of another sign, or of zero on one side, counts as a factor of 100."""
    found = ratio(*pair)
    if found is None:
        return 0.0 if pair[0] == pair[1] or None in pair else 2.0
    return abs(math.log10(found))


def rounded(value, digits=6):
    """A result with `digits` significant digits; None for one that is not a number."""
    if value is None or not math.isfinite(value):
        return None
    if value == 0:
        return 0.0
    return round(value, digits - 1 - int(math.floor(math.log10(abs(value)))))


def compare(title, before, after, items, indicators, values, *, names=None, threshold=1e-6,
            floors=None, noise=None, causes=(), item_causes=None, unexplained=None,
            reference=None, listed=200, keep_items=True, with_bands=True, **more):  # fmt: skip
    """Two sets of results, compared and classified: a whole comparison, checked.

    Every repository's reader ends here, so that all of them count and classify alike.

    - `before`, `after`: `(label, about)`; `items`: `(one, many)`.
    - `indicators`: `[(id, name, short, unit)]`, or dicts with those keys and `reason`.
    - `values`: `{indicator id: {item id: (before, after)}}`, every item that was compared.
    - `names`: `{item id: {"name", "place", "group", "note", "detail"}}`; an item without a
      name is shown by its id.
    - `floors`: per indicator, the size below which a result is near zero; None takes it from
      the results before, 0.0 for all sets none (two builds of the same data).
    - `noise`: `{"between": (label, label), "by": {indicator id: number}, "note"}`, or
      `{"note": ...}` alone where no two builds of one state were compared, or None to say
      nothing about noise.
    - `causes`: causes as `cause()` writes them; the scope of a claim may hold a set of items
      that stays here (`keep_items` false leaves every list of items out of the file).
    - `item_causes`: `{item id: [cause ids]}`, where the repository knows which cause moved
      which item; `unexplained`: `{indicator id: number}` likewise.
    - `reference`: `{"label", "about", "by": {indicator id: {item id: value}}}`.
    - `listed`: how many moved items go into the file with their results, the furthest first.
    - `more`: `step`, `indicator`, `groups`, `rows`, `notes`, `variant`, `variants`.
    """
    names, item_causes = names or {}, item_causes or {}
    meta = [i if isinstance(i, dict) else dict(zip(("id", "name", "short", "unit"), i, strict=True))
            for i in indicators]  # fmt: skip
    ids = [i["id"] for i in meta]
    if floors is None:
        floors = {key: floor_of(b for b, _ in values[key].values()) for key in ids}
    elif not isinstance(floors, dict):
        floors = dict.fromkeys(ids, float(floors))
    levels = (noise or {}).get("by") or {}
    claims = [one["claim"] for one in causes if one.get("claim")]
    classed = (
        classes_of(values, threshold, noise=levels, claims=claims, floors=floors)
        if claims or levels
        else None
    )
    against = (reference or {}).get("by") or {}

    moved_in, written = {}, []
    for one in meta:
        key, pairs = one["id"], values[one["id"]]
        counts = tally(pairs.values(), threshold, floor=floors.get(key, 0.0), bands=with_bands)
        closer = further = None
        if key in against:
            closer = further = 0
            for item_id, (b, a) in pairs.items():
                if moved(b, a, threshold, floors.get(key, 0.0)):
                    way = towards(b, a, against[key].get(item_id))
                    closer, further = closer + (way == "closer"), further + (way == "further")
        for item_id, (b, a) in pairs.items():
            if moved(b, a, threshold, floors.get(key, 0.0)):
                moved_in.setdefault(item_id, []).append(key)
        written.append(
            indicator(
                key,
                one["name"],
                counts,
                short=one.get("short"),
                unit=one.get("unit"),
                reason=one.get("reason"),
                unexplained=(unexplained or {}).get(key) if unexplained is not None else None,
                noise=levels.get(key) if noise and noise.get("between") else None,
                floor=floors.get(key),
                classes=classed["counts"][key] if classed else None,
                closer=closer,
                further=further,
            )  # fmt: skip
        )

    # an item is listed where it moved, or where a stated claim named it and it did not
    shown = set(moved_in)
    if classed:
        shown |= {
            i for key in ids for i, kind in classed["classes"][key].items() if kind == NOT_MOVED
        }

    def pairs_of(item_id):
        return {key: (rounded(values[key][item_id][0]), rounded(values[key][item_id][1]))
                for key in ids if item_id in values[key]}  # fmt: skip

    furthest = sorted(
        shown, key=lambda i: (-max(distance(values[k][i]) for k in ids if i in values[k]), str(i))
    )
    known = {one["id"] for one in causes}
    items_out = []
    for item_id in furthest[:listed]:
        about = names.get(item_id) or {}
        items_out.append(
            item(
                str(item_id),
                about.get("name") or str(item_id),
                pairs_of(item_id),
                place=about.get("place"),
                group=about.get("group"),
                note=about.get("note"),
                causes=sorted(set(item_causes.get(item_id, ())) & known),
                detail=about.get("detail"),
                moved=moved_in.get(item_id, ()),
                classes={
                    k: classed["classes"][k][item_id]
                    for k in ids
                    if item_id in classed["classes"][k]
                }
                if classed
                else None,
                reference={
                    k: rounded(against[k].get(item_id))
                    for k in ids
                    if k in against and item_id in values[k]
                }
                if against
                else None,
            )  # fmt: skip
        )
    compared = len(set().union(*(values[key].keys() for key in ids))) if ids else 0
    said_noise = None
    if noise is not None:
        between = noise.get("between")
        said_noise = {
            "measured": bool(between),
            "between": list(between) if between else None,
            "note": noise.get("note"),
        }
    out_causes = [
        one | {"claim": published(one["claim"], keep_items) if one.get("claim") else None}
        for one in causes
    ]
    said_reference = None
    if reference:
        said_reference = {"label": reference["label"], "about": reference.get("about")}
    return account(
        title, before, after, (items[0], items[1], compared, len(moved_in)), written,
        threshold=threshold, bands=BANDS if with_bands else (), causes=out_causes,
        moved=items_out, moved_not_listed=max(0, len(shown) - listed), noise=said_noise,
        reference=said_reference,
        **more,
    )  # fmt: skip


# ------------------------------------------------------------------------ the breakdown of one item


def detail_errors(data) -> list[str]:
    """What is wrong with the breakdown of one item; nothing when a page can show it.

        {"format": "sentier/before-after-detail/1", "item": "p-1",
         "indicators": {"x:climate": {"unit": "kg CO2 eq", "parts_not_listed": 0, "parts": [
             {"label": "Electricity, at grid", "kind": "background process",
              "before": 0.61, "after": 0.42}]}}}

    A part is whatever the result is made of: an elementary flow, a process of the background,
    the item's own flows. Its two values are its share of the result before and after.
    """
    if not isinstance(data, dict) or data.get("format") != DETAIL_FORMAT:
        return [f"not a breakdown of format {DETAIL_FORMAT}"]
    unknown = sorted(set(data) - {"format", "item", "indicators"})
    found = [f"a key this format does not know: {key}" for key in unknown]
    if not is_text(data.get("item"), MAX_ID):
        found.append("`item` is not an id")
    indicators = data.get("indicators")
    if not isinstance(indicators, dict) or len(indicators) > MAX_INDICATORS:
        return [*found, f"`indicators` is not a table of at most {MAX_INDICATORS}"]
    for key, entry in indicators.items():
        where = f"indicator {key!r}"
        if not is_text(key, MAX_ID) or not isinstance(entry, dict):
            return [*found, "an indicator of a breakdown is not {unit, parts, parts_not_listed}"]
        if set(entry) - {"unit", "parts", "parts_not_listed"}:
            found.append(f"{where}: a key this format does not know")
        if not _optional(entry.get("unit"), MAX_WORD) or not is_count(
            entry.get("parts_not_listed", 0)
        ):
            found.append(f"{where}: `unit` is a short text and `parts_not_listed` a count")
        parts = entry.get("parts")
        if not isinstance(parts, list) or len(parts) > MAX_PARTS:
            found.append(f"{where}: `parts` is not a list of at most {MAX_PARTS}")
            continue
        for part in parts:
            if not (
                isinstance(part, dict)
                and set(part) == {"label", "kind", "before", "after"}
                and is_text(part["label"], MAX_NAME)
                and _optional(part["kind"], MAX_WORD)
                and all(
                    is_result(part[side]) and not isinstance(part[side], bool)
                    for side in ("before", "after")
                )
            ):
                found.append(f"{where}: a part is not {{label, kind, before, after}}")
                break
    return found


def detail(item_id, indicators) -> dict:
    """The breakdown of one item, checked. `indicators` is `{indicator id: (unit, parts,
    parts not listed)}`, a part `(label, kind, before, after)`."""
    data = {
        "format": DETAIL_FORMAT,
        "item": item_id,
        "indicators": {
            key: {
                "unit": unit,
                "parts": [
                    dict(zip(("label", "kind", "before", "after"), part, strict=True))
                    for part in parts
                ],
                "parts_not_listed": left,
            }
            for key, (unit, parts, left) in indicators.items()
        },
    }
    errors = detail_errors(data)
    if errors:
        raise ValueError("not a breakdown: " + "; ".join(errors))
    return data
