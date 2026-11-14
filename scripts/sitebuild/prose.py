"""Markdown to HTML: prose pages, the text of records, tables and step lists."""

import html
import re

import markdown

import community

from .text import esc, plain

EXTENSIONS = ["tables", "fenced_code", "sane_lists"]
ELSEWHERE = re.compile(r"^(https?:|mailto:|#)")
BLOCKS = re.compile(r"<(ul|ol|table|pre|blockquote|h[1-6]|div|hr)\b")


def render(site, text, source, up="", shift=0):
    """Markdown of a prose source to HTML: (html, sections).

    Relative links are resolved against the source file. `sections` are the second-level
    headings, for "On this page". `shift` lowers every heading by that many levels and writes
    no heading ids, for a document shown as a section of another page.
    """
    converter = markdown.Markdown(extensions=EXTENSIONS + ([] if shift else ["toc"]))
    rendered = converter.convert(text)
    sections = []
    if not shift:
        for top in converter.toc_tokens:
            sections += [(t["id"], t["name"]) for t in top["children"]] if top["level"] == 1 else [(top["id"], top["name"])]
    else:
        rendered = re.sub(
            r"<(/?)h([1-6])\b", lambda m: f"<{m.group(1)}h{min(6, int(m.group(2)) + shift)}", rendered
        )

    def rewrite(match):
        link = html.unescape(match.group(1))
        if ELSEWHERE.match(link):
            return match.group(0)
        url, local = site.target(link, source)
        return f'href="{esc((up if local else "") + url)}"'

    rendered = re.sub(r'href="([^"]+)"', rewrite, rendered)
    return finish(rendered), sections


def record_text(site, text, inline=False, up="", link_ids=False, own=None):
    """Markdown of a record. Records hold no raw HTML, no image, no heading and only full
    https links (the build refused anything else before it wrote a page).

    inline=True returns it without the paragraph around it, for a line of a list or a fact.
    link_ids=True turns the number of another finding (F14) into a link to its page.
    """
    rendered = markdown.markdown(text, extensions=EXTENSIONS)
    # Second line of defence behind the validation: whatever the Markdown turned into,
    # a record puts no address on a page that is not a plain https link.
    for address in re.findall(r'(?:href|src)="([^"]*)"', rendered):
        if not community.HTTPS_URL.fullmatch(html.unescape(address)):
            raise ValueError(f"Record text would link to {address!r}; only https addresses are written")
    rendered = finish(rendered)
    if link_ids:
        rendered = link_findings(site, rendered, up, own)
    if not inline:
        return rendered
    if BLOCKS.search(rendered):
        return esc(plain(rendered))  # a list or a table has no place in a line
    return re.sub(r"</p>\s*<p>", "<br>", re.sub(r"^<p>|</p>$", "", rendered.strip()))


def link_findings(site, rendered, up, own=None):
    """F14 in running text becomes a link when that finding exists; never inside a link or code."""
    out, inside = [], 0
    for part in re.split(r"(<[^>]+>)", rendered):
        if part.startswith("<"):
            name = re.match(r"</?([A-Za-z0-9]+)", part)
            if name and name.group(1).lower() in ("a", "code", "pre"):
                inside += -1 if part.startswith("</") else 1
        elif not inside:
            part = re.sub(
                r"\bF[1-9][0-9]*\b",
                lambda m: f'<a href="{up}findings/{m.group(0)}.html">{m.group(0)}</a>'
                if m.group(0) in site.by_id and m.group(0) != own else m.group(0),
                part,
            )
        out.append(part)
    return "".join(out)


def finish(rendered):
    """What every piece of rendered Markdown gets: tables that stack, code blocks a keyboard can scroll."""
    rendered = re.sub(r"<table>.*?</table>", lambda m: table(m.group(0)), rendered, flags=re.S)
    return rendered.replace("<pre>", '<pre tabindex="0">')


# ---------------------------------------------------------------------------- tables


def table(source):
    """Every Markdown table goes through here.

    - first header "Step": a numbered step list with a state per step (steps());
    - otherwise a table whose cells carry their column label, so that it becomes labelled
      rows on a narrow screen instead of squeezing or scrolling sideways.
    """
    head = re.findall(r"<th(?:\s[^>]*)?>(.*?)</th>", source, flags=re.S)
    body = source.split("</thead>", 1)[-1]
    rows = [re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.S) for row in re.findall(r"<tr>(.*?)</tr>", body, flags=re.S)]
    rows = [row for row in rows if row]
    if not head or not rows:
        return source
    if plain(head[0]).lower() == "step" and len(head) >= 3:
        return steps(head, rows)
    classes = [f"cols-{len(head)}"]
    keys = [re.match(r"\s*<strong>(.*?)</strong>", row[0], flags=re.S) for row in rows]
    if all(keys) and max(len(plain(key.group(1))) for key in keys) <= 3:
        classes.append("keyed")  # a letter or a number as the key of each row
    if max(len(plain(row[0])) for row in rows) <= 28:
        classes.append("key-short")
    if len(head) >= 5:
        classes.append("many")  # becomes labelled rows earlier: five columns do not fit a tablet
    labels = [esc(plain(cell)) for cell in head]
    lines = "".join(
        '<tr role="row">' + "".join(
            f'<td role="cell" data-label="{labels[n] if n < len(labels) else ""}">{breakable(cell)}</td>'
            for n, cell in enumerate(row)
        ) + "</tr>"
        for row in rows
    )
    return (
        f'<div class="table-wrap"><table role="table" class="{" ".join(classes)}"><thead role="rowgroup"><tr role="row">'
        + "".join(f'<th role="columnheader" scope="col">{cell}</th>' for cell in head)
        + f'</tr></thead><tbody role="rowgroup">{lines}</tbody></table></div>'
    )


def breakable(cell):
    """A checksum or an address in a cell may break: a column is otherwise as wide as its longest token."""
    def soften(text):
        return re.sub(r"[^\s<>&;]{31,}", lambda m: "<wbr>".join(re.findall(r".{1,16}", m.group(0))), text)

    return "".join(part if part.startswith("<") else soften(part) for part in re.split(r"(<[^>]+>)", cell))


def tone(state):
    """How far a step is, and its text: ("ok" | "part" | "todo", html).

    A state may say it outright with a prefix ("ok: Works", "part: …", "todo: …"), which is
    not shown. Without one the words decide: "works", "done" or "N patches" without a
    reservation is ok; "planned" or "does not exist" is todo; everything else is in part.
    """
    said = re.match(r"\s*(ok|part|todo):\s*", state, flags=re.I)
    if said:
        return said.group(1).lower(), state[said.end():]
    text = plain(state).lower()
    if re.search(r"not exist|^planned|^not started|^no\b", text):
        return "todo", state
    if re.match(r"(works|done|[\d,]+ patches)\b", text) and not re.search(r"\b(not|only|except|part|but)\b", text):
        return "ok", state
    return "part", state


def steps(head, rows):
    """A "Step | What happens | … | State" table as a numbered list with a state per step."""
    said = {"ok": "works", "part": "works in part", "todo": "not yet"}
    items = ""
    for number, row in enumerate(rows, 1):
        # A step keeps the number its row gives it ("7. Exports"), so a list can also be told
        # from its end; a row without a number is counted.
        written = re.match(r"\s*(\d+)\.\s*", row[0])
        number = int(written.group(1)) if written else number
        title = re.sub(r"^\s*\d+\.\s*", "", row[0])
        kind, state = tone(row[-1])
        middle = row[1:-1]
        extra = "".join(
            f'<p class="step-where"><span>{head[n + 2]}</span> {cell}</p>' for n, cell in enumerate(middle[1:]) if cell.strip()
        )
        items += (
            f'<li class="step {kind}"><span class="step-num" aria-hidden="true">{number}</span>'
            f'<h3 class="step-title">{title}</h3>'
            f'<p class="step-state"><span class="visually-hidden">{head[-1]} ({said[kind]}): </span>{state}</p>'
            f'<div class="step-body"><p>{middle[0] if middle else ""}</p>{extra}</div></li>'
        )
    return f'<ol class="steps">{items}</ol>'
