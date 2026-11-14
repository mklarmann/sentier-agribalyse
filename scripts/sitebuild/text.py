"""Small text helpers shared by every template: escaping, dates, counts, link labels."""

import html
import re

MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December")


def esc(value):
    return html.escape(str(value), quote=True)


def plain(markup):
    """The text of a piece of HTML, without its tags."""
    return html.unescape(re.sub(r"<[^>]+>", "", markup)).strip()


def plural(n, word, many=None):
    return f"{thousands(n)} {word if n == 1 else many or word + 's'}"


def thousands(n):
    return f"{n:,}"


def number_word(n, none="no"):
    """none / 1 / 12: a count that reads as a sentence when it is zero."""
    return none if n == 0 else thousands(n)


def comments(n):
    return "no comments yet" if n == 0 else plural(n, "comment")


def day(iso, long=False):
    """2026-10-12 -> <time datetime="2026-10-12">12 Oct 2026</time>; long=True spells the month."""
    if not iso:
        return ""
    year, month, date = iso[:10].split("-")
    name = MONTHS[int(month) - 1]
    shown = f"{int(date)} {name if long else name[:3]} {year}"
    return f'<time datetime="{esc(iso[:10])}">{shown}</time>'


def day_text(iso, long=True):
    """The same date as plain text, for a title, a description or a feed."""
    return plain(day(iso, long))


def words(slug):
    """content-roundtrip -> Content roundtrip"""
    text = str(slug).replace("-", " ").replace("_", " ")
    return text[:1].upper() + text[1:]


def shorten(text, limit=84):
    """A line for a list row: cut at a word, never in the middle of one."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[: limit + 1].rsplit(" ", 1)[0].rstrip(" ,;:(")
    return cut + " …"


def link_label(url, repository):
    """What a link leads to, in a few words: "issue #12" here, "another-repository #3" elsewhere,
    the file name for a file, the host for the rest."""
    hit = re.search(r"/([^/]+)/(?:-/)?(issues|pull|merge_requests)/(\d+)(#[A-Za-z0-9_-]+)?$", url)
    if hit:
        here = url.startswith(repository.rstrip("/") + "/")
        kind = "issue" if hit.group(2) == "issues" else "pull request"
        label = f"{kind} #{hit.group(3)}" if here else f"{hit.group(1)} #{hit.group(3)}"
        return ("comment in " if hit.group(4) and "comment" in hit.group(4) else "") + label
    if "/blob/" in url or "/tree/" in url:
        return url.rstrip("/").rsplit("/", 1)[-1].split("#")[0]
    return url.split("/")[2]


def ext(url, label, classes="ext"):
    """A generated link that leaves the site; the arrow is drawn by the stylesheet."""
    return f'<a class="{classes}" href="{esc(url)}">{label}</a>'
