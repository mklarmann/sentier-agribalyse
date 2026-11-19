# Before and after: comparing two sets of results

This page is the same file in every Sentier dataset repository that uses the comparison. It
says how to read a comparison, how it is counted, what the files hold and how a repository
writes and shows them.

**Where this tool lives.** Since 16 November 2026 its home is a repository of its own,
[sentier-dev/sentier-diagnostics](https://github.com/sentier-dev/sentier-diagnostics), built
on the needs of all the dataset repositories. What is described here is the version it
starts from. Changes to the format are made there, not in a dataset repository; the last
section lists what is known to be missing.

A comparison answers one question: **what did a change to the data do to the results?** The
same items are calculated twice, in the same indicators, and the two sets of results are
set side by side. The two sides can be:

- a provider's data and a patched copy of it;
- published results and a rebuild of them;
- one database built in two ways;
- the state before a contribution and the state with it.

## How to read one

| What you see | What it means |
|---|---|
| **After ÷ before** | The result after, divided by the result before. 1 is no change, 0.5 is half, 2 is double. |
| **Colour of a cell** | Which way the result went and how far the ratio lies from 1. A stronger colour is further away. |
| **≈ 1** | The run counted the value as moved, by less than the digits written in the file show. |
| **Moved** | The two results of an item differ by more than the threshold, relative to the larger of the two. |
| **Near zero** | Both results are too small to say anything about their ratio. Such an item counts as not moved. |
| **Zero or other sign** | One result is zero, or the two have different signs. There is no ratio. The item still counts as moved. |
| **Cause** | A step that was taken on the way from one side to the other, such as a patch, a link or a contribution. |
| **Claim** | What a cause is expected to move: which items, in which indicators, in which direction, and how far at most. |
| **Class** | What a value is, held against the threshold, the noise and the claims. There are six (below). |

The page judges nothing. Whether a change is a correction is said where the change was
decided, not on the page that measures it.

## The six classes

Every value (one item in one indicator) is in exactly one class.

| Class | What it means | What a reviewer does with it |
|---|---|---|
| **unchanged** | The two results agree within the threshold. | Nothing. |
| **within noise** | It moved, by no more than two builds of one state differ. | Nothing: it cannot be told from noise. |
| **as claimed** | It moved, a claim covers it, and it moved in the claim's direction and within its size. | Check the claim, not the value. |
| **off claim** | It moved, a claim covers it, and it moved the other way or further than the claim says. | Look: the cause does something its claim does not say. |
| **not claimed** | It moved, and no claim covers it. | Look: something moved that nobody said would. |
| **claimed, not moved** | A stated claim names it, and it did not move. | Look: the cause does not do what its claim says. |

Three rules decide the cases that could be read two ways:

1. **Noise comes before a claim.** A value that moved no more than the noise is "within
   noise" even where a claim covers it: a move of that size proves nothing about the claim.
2. **A reach that was worked out can be exceeded, never unmet.** A claim is either stated by
   the author of a cause, or worked out from what the cause changed (everything downstream of
   it). A worked-out reach says what *may* move. An item in it that did not move is
   "unchanged", not "claimed, not moved".
3. **A claim without a scope expects nothing to move.** A cause that only renames things
   states such a claim, and any value it moves is "not claimed".

**Noise** is measured, not assumed: two builds of the same state are compared, and what they
differ by in an indicator is that indicator's noise. Where no two builds of one state were
compared, the file says so and no value is counted as within noise.

**A reference** is a third set of results, such as what the provider published. Where a file
names one, the page says whether a value that moved came closer to it or went further.
Closer is not better: a correction may rightly move away from a published number.

## How it is counted

Every run counts with the same functions, in `scripts/runrecord/before_after.py`, so that
two repositories mean the same by the same word.

- `ratio(before, after)` is `after / before`, or nothing where one side is zero, the signs differ or the quotient is no finite number.
- `moved(before, after, threshold, floor)` is true where the two differ by more than `threshold` of the larger.
- `floor_of(values)` is the size below which a result is near zero: 1 % of the median size of the results before.
- `band(before, after, floor)` puts a pair into one of eleven bands.
- `tally(pairs, threshold)` counts one indicator: compared, moved, higher, lower, and the number in each band.
- `noise_of(first, second)` is the largest relative difference between two builds of one state.
- `classify(before, after, threshold, noise, covering, floor)` gives one value its class.
- `compare(...)` does all of it for a whole pair and writes the file's content.

The bands lie equally far from 1 on both sides:

| Below 1 | Around 1 | Above 1 | No ratio |
|---|---|---|---|
| below 0.1 | 0.91 to 1.1 | 1.1 to 1.25 | near zero |
| 0.1 to 0.5 | | 1.25 to 2 | opposite sign or zero |
| 0.5 to 0.8 | | 2 to 10 | |
| 0.8 to 0.91 | | above 10 | |

A run chooses its threshold and its floor, and the file says both. A run that compares two
builds of the same data sets no floor, because every difference counts there. A run that
compares with published results uses the floor, because rounding dominates near zero.

The results in a file are written with six significant digits. The run compares them in
full, so the file also says, for each listed item, in which indicators it moved and in which
class each value is. A page shows that and does not work it out again.

## The files

**A comparison**, `before-after.json`, format `sentier/before-after/2`. The module's own text
describes every key; in short:

| Part | What it holds |
|---|---|
| `title`, `before`, `after` | What is compared, and a sentence about each side. |
| `items` | What an item is called, how many were compared, how many moved in any indicator. |
| `indicators` | Per indicator: compared, moved, higher, lower, not explained, the count per band and per class, its noise and its floor, how many values came closer to the reference or went further, and a reason where one is known for the whole indicator. |
| `causes` | Each step that changed the data: how many rows it changed and of what kind, how many items, how many items it moved, a link, and its claim. |
| `noise` | Whether noise was measured, and between which two builds. |
| `reference` | The third set of results, where there is one. |
| `variant`, `variants` | Where one pair was counted under several rules: which one this file is, and the pages of the others. |
| `rows` | The rows of the data that were compared, that differ, and that nothing explains. |
| `moved` | Items worth a look, each with its two results per indicator, the indicators it moved in, the class of each value, its causes, its reference values, and the file of its breakdown where one was written. An item that a stated claim names and that did not move is listed too. |
| `moved_not_listed` | Such items that are not listed. |
| `notes` | Sentences for below the comparison. |

A file of the first version (`sentier/before-after/1`) has no claims, classes, noise,
reference or variants. It is still read, and it is checked as what it says it is.

**A file is 12 MB at most.** A site reads no larger file of a run, and a page holds the
whole file, so `write` refuses a larger one. A comparison with more to say lists fewer
items (`listed`) and says how many it left out.

**The list of items holds results of single items.** A repository lists only as many as its
data's terms allow it to show, and says how many it left out. A comparison may hold counts
only: `moved` is then empty, and the page shows the indicators and the causes. The same
holds for a claim: a repository may classify with a list of items it does not publish. The
file then holds the claim's words and how many items it reaches, marked as worked out, and
no list.

**A breakdown of one item**, format `sentier/before-after-detail/1`: per indicator, the
parts the result is made of (flows, processes of the background, the item's own flows) with
their share before and after. An item names its file in `detail`, and the page loads it when
the item is opened. Whether a repository may write one is a question of its data's terms: a
breakdown says more about an inventory than a result does.

**A review**, `review.json`, format `sentier/review/1` (`scripts/runrecord/review.py`): the
builds a run made, the causes each contains, what each cause claims, and the pairs of builds
that were compared. Each pair names the page of its comparison. `isolating(index, causes)`
finds the pair that differs by exactly the chosen causes, or the closest pair and what else
it holds. A pair whose first build holds a cause that its second lacks isolates nothing:
the two are more than one change apart.

A file read from a run is data. The checks refuse a key the format does not know, a number
that is not finite, a class or a direction the format does not name, a result of an
indicator the file does not hold, a page name that is a path, and a text that is too long.
A page shows nothing a check did not pass, and one bad file takes no other file of the run
with it.

## Writing one

```python
from runrecord import before_after

data = before_after.compare(
    "The export and the linked copy",
    ("The export", "As it is shipped."),
    ("The linked copy", None),
    ("product", "products"),
    [("x:climate", "Climate change", "Climate", "kg CO2 eq")],  # id, name, short name, unit
    {"x:climate": {"p-1": (2.0, 1.0), "p-2": (5.0, 5.0)}},  # before and after, per item
    names={"p-1": {"name": "Wheat", "place": "FR"}},
    threshold=1e-6,
    floors=0.0,  # or left out: floor_of()
    noise={"between": ("build A", "build B"), "by": {"x:climate": 0.002}},
    causes=[
        before_after.cause(
            "link-1",
            kind="link",
            rows=4,
            items=2,
            claim=before_after.claim(
                "Wheat goes down, by half at most.",
                [before_after.scope(["x:climate"], {"p-1"}, "down", 0.5)],
            ),
        )
    ],
    item_causes={"p-1": ["link-1"]},
    step="comparison",  # the step of the run it belongs to
)
before_after.write(data, folder / before_after.FILE)
```

`compare` counts, classifies, chooses the items to list (those furthest from 1 first) and
checks the result. `keep_items=False` publishes every claim as a count. `account` writes a
file from counts a repository made itself. Both raise an error for a comparison a page could
not show.

A run that built several states writes the index as well:

```python
from runrecord import review

index = review.index(
    "The open contributions, one at a time",
    [review.run("base", "main"), review.run("with-7", "main with contribution 7", ["c-7"])],
    [
        review.cause(
            "c-7",
            kind="contribution",
            title="Sea transport halved.",
            claim=data["causes"][0]["claim"],
        )
    ],
    [review.pair("base", "with-7", page="with-7.html", classes=review.totals(data))],
)
review.write(index, folder / review.FILE)  # and the pair's comparison as with-7.json
```

`scripts/runrecord/example.py` is a made-up review with one value of each class. Every
repository that shows a comparison runs its page and its checks on it.

## Showing one

**On a site that the shared build writes.** The run keeps `before-after.json` in the same
artifact as `run.json` and `transcript.json`. The build then writes the page
`before-after.html`, and the step of the walk through the run that the file names gets a
button that leads to it. The page is in no navigation; it leads back to its step. The same
comparison is a file of the site, `api/v1/before-after.json`. Where the record also holds the
last run that was made for a tag, that run's comparison is `tag-before-after.html`.

Where the artifact also holds `review.json`, the build writes `review.html` and a page for
each pair whose comparison is in the artifact, and the step gets a second button. A run that
did not happen on a public runner brings its files with
`scripts/last_run.py --local ... --before-after before-after.json --review review.json`; the
comparisons of the pairs are read from the folder of the index.

**On a site whose frame is its own.** `scripts/sitebuild/beforeafter.py` has `body(data)`
and `scripts/sitebuild/review.py` has `body(index)`: the page without a frame, as markup. Put
it into the site's own frame and load `assets/before-after.css` with it, and
`assets/before-after.js` or `assets/review.js`. `said` is how a text of the file is shown:
pass a function of the site's own to link its records.

The styles are written with the tokens of the shared stylesheet and with a few of its
classes. A site with a frame of its own defines these, and nothing else is needed:

- tokens: `--index`, `--ink`, `--muted`, `--surface`, `--paper-deep`, `--line`,
  `--line-strong`, `--wait`, `--wait-ink`, `--wait-tint`, `--fail`, `--fail-tint`, `--good`,
  `--radius`, the sizes `--t-xs`, `--t-sm`, `--t-md`, `--t-lg` and the spaces
  `--s2` to `--s6`;
- classes: `button`, `primary`, `linklike`, `card`, `card-label`, `card-meta`, `chip`,
  `chips`, `tag`, `quiet`, `note`, `eyebrow`, `lead`, `crumb`, `plain`, `num`, `table-wrap`,
  `list-none`, `empty`, `field`, `filter-row`, `grow` and `visually-hidden`.

The optional case selector on a full site uses the `sentier-comparison` frame.

A test holds this list against the stylesheet, the two page builders and the two scripts.

Without the script the page is still a page to read: the counts, the classes, the causes
with their claims, each indicator, the first hundred rows of ratios and the results of the
twenty items furthest from 1. The script sorts by any indicator, filters by name, cause,
class and group, shows the results of any listed item, and loads an item's breakdown where
the file names one. Without its script the review lists every pair with what it differs by
and its counts per class; the script finds the pair for the causes a reader ticks.

## What is not in it yet

These are handed to sentier-diagnostics as they stand; none is fixed here.

- **Must and may.** A stated claim is treated as "these values must move", and a claim that
  was worked out as "these may move". A stated claim that only allows a move ("water use
  may move, for any product") is therefore reported as unmet wherever nothing moved. A scope
  entry has to say which it is.
- **Items on one side only.** A result that is missing before or after is not compared, and
  the file does not say how many such items there are.
- **A threshold for what matters.** The one threshold separates the noise of two
  calculations from a change. It does not say whether a change is large enough to matter.
- **A move from zero.** Where the result before is zero a move has no relative size. An
  entry with a largest move then never fits, and one without fits by its direction. No rule
  is written for it.
- **More than one reference**, and whether "closer to the reference" belongs on the page of
  any step but the first.
- **"Only the data differs"** is a fixed sentence of the page. It is not true where one
  database is built in two ways.
- **The script against the rules.** No test runs the page's script and compares it with the
  Python rules; it was checked by hand.
- **A reason for a single item**, beyond the item's `note`.
- **A comparison of more than two states at once.** A review is a set of pairs; three states
  side by side on one page is not a thing the format describes.
- **Noise per item.** The noise is one number per indicator, the largest difference between
  two builds of one state. An indicator in which a few items are unstable and the rest are
  not is described too coarsely by it.
