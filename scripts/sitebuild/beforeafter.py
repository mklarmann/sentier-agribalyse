"""The page of a comparison: two sets of results over the same items, before and after.

It shows one file, `before-after.json` (`scripts/runrecord/before_after.py`), as it is: every
number on the page is one the file states or the quotient of two it states, and every name is
the file's own. The page knows no dataset and no tool.

`body` is the page without a frame: a site whose frame is its own puts it into that frame,
with `assets/before-after.css` and `assets/before-after.js` beside it. It needs nothing but
this file, `text.py` and the format. `page` is the same in the frame of a site that the
shared build writes.

Without the script it is a page to read: the counts, what caused the changes and what each
cause claimed, each indicator, and the items that moved furthest with their ratios and their
results. The script (`assets/before-after.js`) sorts and filters the items and shows the
results of any of them.

What the page shows of one pair of results is `after / before`: 1 is no change. Its colour
says how far from 1 it lies, and on which side. Where the file puts each value into a class
(as claimed, not claimed, ...), a cell carries the mark of its class; the page never works a
class out itself.
"""

import json
import math

from runrecord import before_after

from .text import esc, plural, thousands

STYLE, SCRIPT = "assets/before-after.css", "assets/before-after.js"
#: Items the page holds as markup, for a reader without the script; the script shows the rest.
STATIC_ROWS = 100
STATIC_DETAILS = 20
#: How each class is marked in a cell and counted in a bar: a name for the stylesheet.
KINDS = {
    before_after.UNCHANGED: "unchanged", before_after.NOISE: "noise", before_after.AS_CLAIMED: "claimed",
    before_after.OFF_CLAIM: "off", before_after.NOT_CLAIMED: "unclaimed", before_after.NOT_MOVED: "unmet",
}
SAID = {
    before_after.UNCHANGED: "the two results agree within the threshold",
    before_after.NOISE: "moved no more than two builds of one state differ",
    before_after.AS_CLAIMED: "moved, inside a claim, in its direction and within its size",
    before_after.OFF_CLAIM: "moved, inside a claim, in another direction or further than it says",
    before_after.NOT_CLAIMED: "moved, and no claim covers it",
    before_after.NOT_MOVED: "a stated claim covers it, and it did not move",
}
#: The classes that ask for a reviewer's eye.
ODD = (before_after.OFF_CLAIM, before_after.NOT_CLAIMED, before_after.NOT_MOVED)


def number(value):
    """A result as a reader takes it in: three significant digits."""
    if value is None:
        return "not stated"
    if value == 0:
        return "0"
    size = abs(value)
    if size < 0.001 or size >= 100000:
        mantissa, exponent = f"{value:.2e}".split("e")
        return f"{mantissa} × 10<sup>{int(exponent)}</sup>"
    # three significant digits, never as a power of ten here: 999.7 is "1,000"
    shown = float(f"{value:.3g}")
    return f"{shown:.3g}" if abs(shown) < 1000 else thousands(round(shown))


def ratio_text(found):
    """A ratio of a value that moved: three significant digits, and more where three would
    read "1", so that a move is never shown as no change."""
    text = number(found)
    for digits in (4, 5, 6, 8):
        if text != "1":
            break
        text = f"{found:.{digits}g}"
    return text


def has_moved(item, key, pair, threshold):
    """Whether an item moved in an indicator: as the file says, where it says (the results in
    it are rounded, so working it out again could differ); else from the two results."""
    if item is not None and item.get("moved") is not None:
        return key in item["moved"]
    return before_after.moved(pair[0], pair[1], threshold or 0.0)


def percent(before, after):
    """The change from `before` to `after` in percent, as text; None where there is none to say."""
    if before in (None, 0) or after is None:
        return None
    return share((after - before) / abs(before), signed=True)


def share(value, signed=False):
    """A share as a percentage a reader takes in: 0.025 is "2.5 %"."""
    size = abs(value) * 100
    digits = 0 if size >= 10 else 1 if size >= 1 else 2 if size >= 0.01 else 6
    text = f"{size:.{digits}f}".rstrip("0").rstrip(".") if digits > 2 else f"{size:.{digits}f}"
    sign = ("+" if value > 0 else "−" if value < 0 else "") if signed else ""
    return f"{sign}{text} %"


def capital(text):
    return text[:1].upper() + text[1:]


def cell(pair, moved, kind=None):
    """One cell of the grid: the ratio of a pair of results, and how it is drawn. `moved` is
    whether the value moved (`has_moved`), `kind` the class the file gives it, if any."""
    before, after = pair if pair else (None, None)
    if before is None or after is None:
        return '<td class="num ba-cell is-none"></td>'
    mark = f' k-{KINDS[kind]}" data-class="{esc(kind)}' if kind else ""
    said = f"{capital(kind)}: {SAID[kind]}" if kind else None
    found = before_after.ratio(before, after)
    if not moved:
        # not counted as moved: the ratio is shown as it is, and the cell is not coloured
        same = found is None or number(found) == "1"
        title = said or ("No change" if same else "Not counted as moved: within the threshold, or near zero on both sides")
        return f'<td class="num ba-cell is-same{mark}" title="{esc(title)}">{"1" if same else number(found)}</td>'
    if found is None:
        title = "Zero, or of the other sign, on one side: no ratio" + (f". {said}" if said else "")
        return f'<td class="num ba-cell is-opposite{mark}" title="{esc(title)}">–</td>'
    if after == before:
        # counted as moved by the run, by less than the results as written show
        title = "Moved by less than the digits written here show" + (f". {said}" if said else "")
        return f'<td class="num ba-cell is-slight{mark}" title="{esc(title)}">≈ 1</td>'
    depth = max(0.12, min(1.0, abs(max(-1.0, min(1.0, math.log10(found)))) * 2.2))
    # the side is where the result went, not where the quotient lies: of two results below
    # zero the lower one gives the larger quotient
    side = "above" if after > before else "below"
    title = f' title="{esc(said)}"' if said else ""
    return f'<td class="num ba-cell is-{side}{mark}"{title} style="--d:{depth:.2f}">{ratio_text(found)}</td>'


def as_data(text):
    """JSON as the content of a script element: no `<`, `>` or `&` in it, so that no text of a
    file can end the element, open a comment in it or be read as markup."""
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def plain(text):
    """A text of the file as it is, escaped: how `body` shows one where the site gives it no
    way of its own to read a text (links to its records, names shown as code)."""
    return esc(text)


def slug(text):
    return "".join(c if c.isalnum() else "-" for c in str(text)).strip("-").lower()


def count(value):
    return "" if value is None else thousands(value)


def a(word):
    return "an" if word[:1].lower() in "aeiou" else "a"


def words(data):
    """What an indicator is called in this file: `(one, many)`."""
    named = data.get("indicator") or {}
    return named.get("one", "indicator"), named.get("many", "indicators")


# ------------------------------------------------------------------ claims and classes


def claim_line(claim, items, said):
    """What a cause claims, under its title: the claim's own words, and how far it reaches."""
    if not claim:
        return ""
    reach = claim.get("reach")
    how = ""
    if claim.get("derived"):
        how = " Worked out from what the cause changed, not stated by its author"
        how += f": it reaches {plural(reach, items['one'], items['many'])}." if reach is not None else "."
    elif reach is not None:
        how = f" It names {plural(reach, items['one'], items['many'])}."  # escaped below
    elif not claim.get("scope"):
        how = " It expects nothing to move."
    return f'<span class="ba-claim"><strong>Claim.</strong> {said(claim["text"])}{esc(how)}</span>'


def class_totals(data):
    """The values of the file per class, over all indicators; None where it gives no classes."""
    if not any(i.get("classes") for i in data["indicators"]):
        return None
    found = dict.fromkeys(before_after.CLASSES, 0)
    for indicator in data["indicators"]:
        for kind, n in (indicator.get("classes") or {}).items():
            found[kind] += n
    return found


def verdict(totals, noise):
    """One sentence on what the classes add up to. It counts; it does not judge the change."""
    odd = totals[before_after.OFF_CLAIM] + totals[before_after.NOT_CLAIMED]
    unmet, claimed, within = totals[before_after.NOT_MOVED], totals[before_after.AS_CLAIMED], totals[before_after.NOISE]
    if odd:
        kind = "odd"
        text = f"{plural(odd, 'value')} moved outside what the causes claim."
        more = "Either a claim is incomplete, or something moved that should not have."
    elif unmet:
        kind = "odd"
        text = f"{plural(unmet, 'value')} that a claim names did not move."
        more = "Either the claim says too much, or the change did not take effect."
    elif within and not claimed:
        kind = "open"
        text = f"{plural(within, 'value')} moved, and none can be told from noise."
        more = "Two builds of the same state differ by as much, so this comparison cannot show what the change did."
    elif claimed:
        kind = "fine"
        text = f"{plural(claimed, 'value')} moved, all as claimed."
        more = f"{plural(within, 'value')} more moved within noise." if within else ""
    else:
        kind = "fine"
        text = "No value moved."
        more = ""
    still = f" {thousands(totals[before_after.UNCHANGED])} did not move." if totals[before_after.UNCHANGED] else ""
    return f'<p class="ba-verdict is-{kind}"><strong>{text}</strong> {more}{still}</p>'


def classes_block(data):
    """The six classes with their counts, and the sentence they add up to."""
    totals = class_totals(data)
    if totals is None:
        return ""
    cards = "".join(
        f'<div class="ba-class k-{KINDS[kind]}{" is-none" if not totals[kind] else ""}" data-ba-class="{esc(kind)}">'
        f"<dt>{esc(capital(kind))}</dt><dd>{thousands(totals[kind])}</dd><p>{esc(capital(SAID[kind]))}.</p></div>"
        for kind in before_after.CLASSES
    )
    return (
        '<h2 id="classes">What moved, against what was claimed</h2>'
        f"<p>Each value is one {esc(data['items']['one'])} in one {esc(words(data)[0])}.</p>"
        f"{verdict(totals, data.get('noise'))}"
        f'<dl class="ba-classes">{cards}</dl>'
    )


def class_bar(indicator):
    """The values of one indicator that are not unchanged, by class, as one bar."""
    counted = {k: n for k, n in (indicator.get("classes") or {}).items() if n and k != before_after.UNCHANGED}
    total = sum(counted.values())
    if not total:
        return ""
    parts = "".join(
        f'<span class="k-{KINDS[kind]}" style="flex:{counted[kind]} 0 0" title="{esc(capital(kind))}: {thousands(counted[kind])}"></span>'
        for kind in before_after.CLASSES if kind in counted
    )
    said = "; ".join(f"{kind}: {thousands(counted[kind])}" for kind in before_after.CLASSES if kind in counted)
    return f'<span class="ba-strip ba-kinds" role="img" aria-label="{esc(said)}">{parts}</span>'


def setting(data, said):
    """What the comparison was measured against: the noise of the builds, and the reference."""
    lines = []
    noise = data.get("noise")
    if noise:
        if noise["measured"]:
            between = " and ".join(esc(name) for name in noise["between"]) if noise.get("between") else "two builds of one state"
            text = f"<strong>Noise was measured</strong> between {between}: a value that moved no more than those two differ cannot be told from noise."
        else:
            text = "<strong>Noise was not measured:</strong> no two builds of one state were compared, so no value is counted as within noise."
        lines.append(text + (f" {said(noise['note'])}" if noise.get("note") else ""))
    reference = data.get("reference")
    if reference:
        about = f" {said(reference['about'])}" if reference.get("about") else ""
        lines.append(
            f"<strong>Reference: {esc(reference['label'])}.</strong>{about} The page says whether a value that moved came "
            "closer to it or went further. Closer is not better: a correction may rightly move away."
        )
    return '<ul class="plain ba-setting">' + "".join(f"<li>{line}</li>" for line in lines) + "</ul>" if lines else ""


def variants(data):
    """Where one pair was counted under several rules: the others, by name."""
    listed = data.get("variants") or []
    if len(listed) < 2:
        return ""
    current = (data.get("variant") or {}).get("id")
    links = " ".join(
        f'<span class="chip" aria-current="true">{esc(one["label"])}</span>' if one["id"] == current
        else f'<a class="chip" href="{esc(one["page"])}">{esc(one["label"])}</a>'
        for one in listed
    )
    return f'<p class="chips ba-variants"><span class="card-label">Counted as</span> {links}</p>'


# ------------------------------------------------------------------ the tables


def causes_table(data, said):
    causes = data.get("causes") or []
    if not causes:
        return ""
    rows_word = (data.get("rows") or {}).get("many", "rows")
    many = esc(data["items"]["many"])
    counted = any(cause.get(key) is not None for cause in causes for key in ("rows", "items", "moved"))
    body = ""
    for cause in causes:
        changed = ", ".join(f"{thousands(n)} × {esc(what)}" for what, n in sorted(cause.get("changed", {}).items()))
        title = f'<span class="ba-about">{said(cause["title"])}</span>' if cause.get("title") else ""
        title += claim_line(cause.get("claim"), data["items"], said)
        kind = f'<span class="tag">{esc(cause["kind"])}</span> ' if cause.get("kind") else ""
        name = f'<code>{esc(cause["id"])}</code>'
        if cause.get("link"):
            name = f'<a href="{esc(cause["link"])}">{name}</a>'
        body += f'<tr id="cause-{esc(slug(cause["id"]))}"><th scope="row">{kind}{name}{title}</th>' + (
            f'<td class="num">{count(cause.get("rows"))}</td><td>{changed}</td>'
            f'<td class="num">{count(cause.get("items"))}</td><td class="num">{count(cause.get("moved"))}</td>'
            if counted else ""
        ) + "</tr>"
    head = (
        f'<th scope="col" class="num">{esc(rows_word.capitalize())} changed</th><th scope="col">What was changed</th>'
        f'<th scope="col" class="num">{many.capitalize()} changed</th><th scope="col" class="num">{many.capitalize()} whose results moved</th>'
        if counted else ""
    )
    return (
        '<h2 id="causes">What caused the changes</h2>'
        "<p>Every difference between the two sides must have a cause: a step that was taken on the way from one to the other. "
        "A step that changes no result is listed too.</p>"
        f'<div class="table-wrap"><table class="ba-table"><thead><tr><th scope="col">Cause</th>{head}'
        f"</tr></thead><tbody>{body}</tbody></table></div>"
    )


def strip(indicator, bands):
    """The items of one indicator by band, as one bar: far below 1 on the left, far above on
    the right, the band around 1 in the middle. Read by its title; the table has the counts."""
    counted = indicator.get("bands")
    if not counted or not sum(counted):
        return ""
    total = sum(counted)
    parts = ""
    for name, n in zip(bands, counted):
        if not n:
            continue
        kind = "mid" if name in (before_after.MIDDLE, before_after.NEAR_ZERO) else "odd" if name == before_after.OPPOSITE else "off"
        parts += f'<span class="is-{kind}" style="flex:{n} 0 0" title="{esc(name)}: {thousands(n)}"></span>'
    said = "; ".join(f"{name}: {thousands(n)}" for name, n in zip(bands, counted) if n)
    return f'<span class="ba-strip" role="img" aria-label="{esc(said)} (of {thousands(total)})">{parts}</span>'


def indicators_table(data, said, word):
    bands = data.get("bands") or []
    many = esc(data["items"]["many"])
    has = lambda key: any(i.get(key) is not None for i in data["indicators"])  # noqa: E731
    explained, banded, classed, noisy = has("unexplained"), any(i.get("bands") for i in data["indicators"]), has("classes"), has("noise")
    against = has("closer") or has("further")
    body = ""
    for i in data["indicators"]:
        unit = f' <span class="quiet">{esc(i["unit"])}</span>' if i.get("unit") else ""
        reason = f'<span class="ba-about">{said(i["reason"])}</span>' if i.get("reason") else ""
        level = i.get("noise")
        body += (
            f'<tr class="{"is-moved" if i["moved"] else "is-still"}"><th scope="row">{esc(i["name"])}{unit}{reason}</th>'
            f'<td class="num">{thousands(i["compared"])}</td><td class="num"><strong>{thousands(i["moved"])}</strong></td>'
            f'<td class="num">{thousands(i["lower"])}</td><td class="num">{thousands(i["higher"])}</td>'
            + (f'<td class="num">{count(i.get("unexplained"))}</td>' if explained else "")
            + (f"<td>{class_bar(i)}</td>" if classed else "")
            + (f'<td class="num">{"" if level is None else "none" if not level else "up to " + share(level)}</td>' if noisy else "")
            + (f'<td class="num">{count(i.get("closer"))}</td><td class="num">{count(i.get("further"))}</td>' if against else "")
            + (f"<td>{strip(i, bands)}</td>" if banded else "")
            + "</tr>"
        )
    still = sum(1 for i in data["indicators"] if not i["moved"])
    none = f" In {esc(plural(still, word[0], word[1]))} nothing moved." if still else ""
    return (
        f'<h2 id="indicators">Per {esc(word[0])}</h2>'
        f"<p>How many {many} moved in each {esc(word[0])}, and in which direction.{none}</p>"
        f'<div class="table-wrap"><table class="ba-table"><thead><tr><th scope="col">{esc(word[0].capitalize())}</th>'
        '<th scope="col" class="num">Compared</th><th scope="col" class="num">Moved</th>'
        '<th scope="col" class="num">Lower after</th><th scope="col" class="num">Higher after</th>'
        + ('<th scope="col" class="num">Not explained</th>' if explained else "")
        + ('<th scope="col">Moved, by class</th>' if classed else "")
        + ('<th scope="col" class="num">Noise</th>' if noisy else "")
        + ('<th scope="col" class="num">Closer to the reference</th><th scope="col" class="num">Further</th>' if against else "")
        + ('<th scope="col">After ÷ before, by band</th>' if banded else "")
        + f"</tr></thead><tbody>{body}</tbody></table></div>"
    )


def detail(data, item, word):
    """The results of one item: before, after and the change, per indicator; and, where the
    file gives them, the class of each value and the reference."""
    threshold = data.get("threshold") or 0.0
    kinds, against = item.get("classes") or {}, item.get("reference") or {}
    rows = ""
    for i in data["indicators"]:
        pair = item["values"].get(i["id"])
        if not pair:
            continue
        before, after = pair
        changed = has_moved(item, i["id"], pair, threshold)
        kind = kinds.get(i["id"])
        rows += (
            f'<tr class="{"is-moved" if changed else "is-still"}"><th scope="row">{esc(i["name"])}</th>'
            f'<td class="num">{number(before)}</td><td class="num">{number(after)}</td>'
            f'<td class="num">{(percent(before, after) or "") if changed else "no change"}</td>'
            + (f'<td><span class="ba-kind k-{KINDS[kind]}">{esc(kind)}</span></td>' if kinds and kind else "<td></td>" if kinds else "")
            + (f'<td class="num">{number(against[i["id"]]) if against.get(i["id"]) is not None else ""}</td>' if against else "")
            + f'<td class="quiet">{esc(i.get("unit") or "")}</td></tr>'
        )
    reference = (data.get("reference") or {}).get("label", "Reference")
    return (
        f'<div class="table-wrap"><table class="ba-table ba-values"><thead><tr><th scope="col">{esc(word[0].capitalize())}</th>'
        f'<th scope="col" class="num">{esc(data["before"]["label"])}</th><th scope="col" class="num">{esc(data["after"]["label"])}</th>'
        '<th scope="col" class="num">Change</th>'
        + ('<th scope="col">Class</th>' if kinds else "")
        + (f'<th scope="col" class="num">{esc(reference)}</th>' if against else "")
        + f'<th scope="col">Unit</th></tr></thead><tbody>{rows}</tbody></table></div>'
    )


def name_of(item):
    return esc(item["name"]) + (f' <span class="quiet">{esc(item["place"])}</span>' if item.get("place") else "")


def grid(data, word, details=""):
    """The items that moved, one row each, one column per indicator: after ÷ before.
    `details` is the folder, from the page, that holds the breakdowns the items name."""
    listed = data.get("moved") or []
    one, many = data["items"]["one"], data["items"]["many"]
    left = data.get("moved_not_listed", 0)
    if not listed:
        text = (
            f"{esc(capital(plural(left, one, many)))} moved; this file lists none of them."
            if left else f"No {esc(one)} moved."
        )
        return f'<h2 id="moved">The {esc(many)} that moved</h2><p class="list-none">{text}</p>'
    threshold = data.get("threshold")
    head = "".join(
        f'<th scope="col" class="num" data-indicator="{esc(i["id"])}"><abbr title="{esc(i["name"])}'
        + (f' ({esc(i["unit"])})' if i.get("unit") else "")
        + f'">{esc(i.get("short") or i["name"])}</abbr></th>'
        for i in data["indicators"]
    )
    rows = ""
    for position, item in enumerate(listed[:STATIC_ROWS]):
        kinds = item.get("classes") or {}
        cells = "".join(
            cell(pair := item["values"].get(i["id"]), bool(pair) and None not in pair and has_moved(item, i["id"], pair, threshold),
                 kinds.get(i["id"]))
            for i in data["indicators"]
        )
        why = ", ".join(f"<code>{esc(c)}</code>" for c in item.get("causes") or ())
        rows += (
            f'<tr data-i="{position}"><th scope="row" class="ba-name" title="{esc(item["name"])}">{name_of(item)}'
            + (f'<span class="ba-why">{why}</span>' if why else "")
            + f"</th>{cells}</tr>"
        )
    shown_details = "".join(
        f'<details class="ba-item"><summary>{name_of(item)}</summary>{detail(data, item, word)}</details>'
        for item in listed[:STATIC_DETAILS]
    )
    more = len(listed) - STATIC_ROWS
    shown = (
        f"The {thousands(len(listed))} that moved furthest are listed; {thousands(left)} more moved." if left
        else f"All {thousands(len(listed))} are listed." if len(listed) > 1 else ""
    )
    # an item a stated claim names is listed though it did not move: the reader is told
    still = sum(1 for item in listed if item.get("moved") == [])
    if still:
        shown += (
            f" {thousands(still)} of them did not move and {'is' if still == 1 else 'are'} "
            f"listed because a stated claim names {'it' if still == 1 else 'them'}."
        )
    if more > 0:
        shown += f" Without the script the page shows the first {STATIC_ROWS}."
    classed = any(item.get("classes") for item in listed)
    keys = ("before", "after", "items", "threshold", "indicators", "groups", "causes", "moved", "reference")
    payload = json.dumps(
        {key: data.get(key) for key in keys} | {"word": list(word), "kinds": KINDS, "said": SAID, "details": details},
        ensure_ascii=False, separators=(",", ":"), allow_nan=False,
    )
    payload = as_data(payload)
    legend = (
        '<p class="ba-legend" aria-hidden="true"><span><span class="ba-key is-below"></span>lower after</span> '
        '<span><span class="ba-key is-above"></span>higher after</span> '
        '<span><span class="ba-key is-opposite"></span>zero or other sign on one side</span> '
        '<span><span class="ba-key is-same"></span>no change</span>'
        + ("".join(f' <span><span class="ba-key k-{KINDS[kind]}"></span>{esc(kind)}</span>' for kind in ODD) if classed else "")
        + "</p>"
    )
    return (
        f'<h2 id="moved">The {esc(many)} that moved</h2>'
        f'<p>Each cell is the result after, divided by the result before, for that {esc(one)} and {esc(word[0])}: '
        f"1 is no change, 0.5 is half, 2 is double. {shown}</p>"
        '<div class="ba-board" data-before-after>'
        '<div class="ba-controls" hidden><div class="filter-row">'
        '<label class="field grow"><span>Name</span><input type="search" data-ba-filter placeholder="Filter by name" autocomplete="off" spellcheck="false"></label>'
        '<label class="field" data-ba-cause-field hidden><span>Cause</span><select data-ba-cause><option value="">Any</option></select></label>'
        '<label class="field" data-ba-group-field hidden><span>Group</span><select data-ba-group><option value="">All</option></select></label>'
        '<label class="field" data-ba-kind-field hidden><span>Class</span><select data-ba-kind><option value="">Any</option></select></label>'
        '</div><p class="ba-count" data-ba-count role="status" aria-live="polite"></p></div>'
        f"{legend}"
        f'<div class="table-wrap ba-grid-wrap" role="region" aria-label="After divided by before, per {esc(one)} and {esc(word[0])}" tabindex="0">'
        f'<table class="ba-grid" style="--n:{len(data["indicators"])}"><thead><tr><th scope="col" class="ba-name">{esc(one.capitalize())}</th>{head}</tr></thead>'
        f"<tbody>{rows}</tbody></table></div>"
        '<p class="ba-more"><button class="button" type="button" data-ba-more hidden>Show more</button></p>'
        '<div class="ba-detail" data-ba-detail hidden tabindex="-1" role="region" aria-labelledby="ba-detail-title"></div>'
        f'<div class="ba-static"><h3>Results of the {esc(many)} that moved furthest</h3>{shown_details}</div>'
        f'<script type="application/json" data-ba-data>{payload}</script></div>'
    )


def reading(data, word):
    threshold = data.get("threshold")
    one, many = esc(data["items"]["one"]), esc(data["items"]["many"])
    moved = (
        f"<li>A {one} <strong>moved</strong> in {a(word[0])} {esc(word[0])} when its two results differ by more than "
        f"{share(threshold)} of the larger of the two. A smaller difference is the noise of two separate calculations.</li>"
        if threshold else f"<li>A {one} <strong>moved</strong> when its two results differ.</li>"
    )
    classed = (
        "<li>A <strong>claim</strong> says what a cause is expected to move. Each value is then one of six: unchanged, "
        "within noise, as claimed, off claim, not claimed, or claimed and not moved. A claim that was worked out from "
        "what the cause changed expects nothing to move; only a claim its author stated can be unmet.</li>"
        if class_totals(data) is not None else ""
    )
    return (
        '<h2 id="reading">How to read this page</h2><ul class="plain">'
        f"<li>Both sides were calculated the same way, over the same {many} and with the same {esc(word[1])}. Only the data differs.</li>"
        f"{moved}{classed}"
        "<li>A cell shows <strong>after ÷ before</strong>. The further it lies from 1, the stronger its colour.</li>"
        "<li>A result of zero on one side, or of the other sign, has no ratio. Where both results are too small to say "
        "anything about their ratio, they count as not moved.</li>"
        "<li>The page judges nothing: whether a change is a correction is said where the change was decided, not here.</li>"
        "</ul>"
    )


def body(data, back=None, said=plain, file=None, up="", details="", opening="", diagnostics=""):
    """The page of one comparison, without a frame. `back` is `(address, label)` of where
    the reader came from, `said` how a text of the file is shown, `file` the address of the
    comparison as a file, `up` the way from the page to the folder that holds `assets/`,
    `details` the folder that holds the breakdowns of single items, where the file names any."""
    word = words(data)
    items, rows = data["items"], data.get("rows")
    one, many = items["one"], items["many"]
    figures = [
        (thousands(items["compared"]), f"{many} compared"),
        (thousands(items["moved"]), f"{many if items['moved'] != 1 else one} moved"),
        (thousands(len(data["indicators"])), word[1] if len(data["indicators"]) != 1 else word[0]),
    ]
    if rows:
        figures += [
            (thousands(rows["compared"]), f"{rows['many']} compared"),
            (thousands(rows["differ"]), "differ"),
            (thousands(rows["unexplained"]), "not explained"),
        ]
    tally = '<dl class="ba-figures">' + "".join(f"<div><dt>{esc(label)}</dt><dd>{value}</dd></div>" for value, label in figures) + "</dl>"
    sides = '<div class="ba-sides">' + "".join(
        f'<div class="card"><p class="card-label">{label}</p><p class="ba-side">{esc(side["label"])}</p>'
        + (f'<p class="card-meta">{said(side["about"])}</p>' if side.get("about") else "")
        + "</div>"
        for label, side in (("Before", data["before"]), ("After", data["after"]))
    ) + "</div>"
    crumb = f'<p class="crumb"><a href="{esc(back[0])}">{esc(back[1])}</a></p>' if back else ""
    notes = "".join(f"<li>{said(note)}</li>" for note in data.get("notes") or ())
    as_file = (
        f'<p class="note">The same comparison as a file: <a href="{esc(file)}"><code>{esc(file)}</code></a>.</p>' if file else ""
    )
    measurements = (
        f"{variants(data)}{tally}{sides}{setting(data, said)}"
        + classes_block(data)
        + causes_table(data, said)
        + indicators_table(data, said, word)
        + grid(data, word, details)
        + (f'<h2 id="notes">Notes</h2><ul class="plain">{notes}</ul>' if notes else "")
        + reading(data, word)
        + as_file
        + f'<script src="{up}{SCRIPT}" defer></script>'
    )
    if diagnostics:
        measurements = f'<details class="ba-pair"><summary>Before-and-after measurements</summary>{measurements}</details>'
    return f'{crumb}<p class="eyebrow">Before and after</p><h1>{esc(data["title"])}</h1>{opening}{diagnostics}{measurements}'


def page(site, data, name, back=None, current=None, review_section="", diagnostics=None):
    """The whole page of one comparison, in the frame of a site the shared build writes: a
    text of the file links the findings it names, as everywhere on such a site."""
    from . import shell
    from .lastrun import inline

    title = (data or diagnostics)["title"]
    head = f'<link rel="stylesheet" href="{STYLE}">'
    jumps = []
    diagnostics_body = ""
    if diagnostics:
        from importlib.metadata import distribution

        from sentier_diagnostics import page as diagnostics_page

        for asset, source in diagnostics_page.assets().items():
            site.copy(source, "assets/" + asset)
        package = distribution("sentier-diagnostics")
        for notice in package.files or ():
            if notice.name in ("LICENSE", "NOTICE") and notice.parent.name == "licenses":
                site.copy(package.locate_file(notice), f"assets/diagnostics-{notice.name}.txt")
        head += '<link rel="stylesheet" href="assets/diagnostics.css"><script src="assets/diagnostics.js" defer></script>'
        diagnostics_body = '<section aria-labelledby="diagnostics"><h2 id="diagnostics">Diagnostics by build step</h2>'
        diagnostics_body += diagnostics_page.body(diagnostics, title=False) + "</section>"
        jumps.append(("diagnostics", "Build-step diagnostics"))
    if data:
        many = data["items"]["many"]
        jumps.append(("moved", f"Changed {many}"))
        if data.get("causes"):
            jumps.append(("causes", "Causes"))
        jumps.append(("indicators", f"By {words(data)[0]}"))
    if review_section:
        jumps.append(("review", "Review individual changes"))
    opening = ""
    if site.build_views and len(jumps) > 1:
        links = "".join(f'<a href="#{anchor}">{esc(label)}</a>' for anchor, label in jumps)
        opening = f'<nav class="ba-sections" aria-label="Comparison sections">{links}</nav>'
    described = title
    if data:
        described = f'{title}: which {many} moved, in which {words(data)[1]}, and what caused it.'
        inner = body(data, back, lambda text: inline(site, text, ""), f'api/v1/{name.removesuffix(".html")}.json',
                     opening=opening, diagnostics=diagnostics_body)
    else:
        crumb = f'<p class="crumb"><a href="{esc(back[0])}">{esc(back[1])}</a></p>' if back else ""
        inner = f'{crumb}<h1>{esc(title)}</h1>{opening}{diagnostics_body}'
    framed = f'<div class="wrap page ba-page"><article class="prose wide">{inner}{review_section}</article></div>'
    return shell.shell(site, title, framed, current or name, page=name, description=described, head=head)
