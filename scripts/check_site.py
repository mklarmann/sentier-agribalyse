"""Check the built site: links, anchors, page basics, data files, and that no inventory file is in it.

Run: python3 scripts/check_site.py _site

Fails on: a local link or anchor that leads nowhere, an address that is neither https nor
mailto, an id used twice on a page, a page without a language, a title, a description or
exactly one first-level heading, a JSON or XML file that does not parse, a sitemap entry
without a file, and any file type an inventory export would have.
"""

import argparse
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree

EXPORTS = {".parquet", ".npz", ".bw2package", ".sqlite", ".db", ".csv", ".gz", ".zip", ".xlsx", ".spold"}
XML_FILES = {"feed.xml", "sitemap.xml"}  # the provider's release is XML too: no other XML file is published
SITEMAP = "{http://www.sitemaps.org/schemas/sitemap/0.9}loc"


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.ids, self.h1 = [], [], 0
        self.lang = self.description = self.canonical = None
        self.title, self.redirect, self._in_title = "", False, False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        for key in ("href", "src", "action"):
            if attrs.get(key) is not None:
                self.links.append(attrs[key])
        if tag == "html":
            self.lang = attrs.get("lang")
        elif tag == "h1":
            self.h1 += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "meta" and attrs.get("name") == "description":
            self.description = attrs.get("content")
        elif tag == "meta" and attrs.get("http-equiv") == "refresh":
            self.redirect = True
        elif tag == "link" and attrs.get("rel") == "canonical":
            self.canonical = attrs.get("href")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def check(root):
    root = Path(root)
    pages, errors = {}, []
    for path in sorted(root.rglob("*")):
        if path.suffix in EXPORTS:
            errors.append(f"Inventory or binary export must not enter site: {path.name}")
        if path.suffix == ".html":
            page = Page()
            page.feed(path.read_text())
            pages[path.resolve()] = page
        elif path.suffix == ".json":
            try:
                json.loads(path.read_text())
            except ValueError as error:
                errors.append(f"{path.relative_to(root)}: not valid JSON ({error})")
        elif path.suffix == ".xml":
            if path.relative_to(root).as_posix() not in XML_FILES:
                errors.append(f"{path.relative_to(root)}: the only XML files of the site are {' and '.join(sorted(XML_FILES))}")
                continue
            try:
                ElementTree.parse(path)
            except ElementTree.ParseError as error:
                errors.append(f"{path.relative_to(root)}: not well-formed XML ({error})")
    index = pages.get((root / "index.html").resolve())
    if not index:
        errors.append("Site lacks index.html or pages")
    # Where the site lives on its host (the path of its address): the page for missing addresses links from there.
    base = (index.canonical or "").rsplit("/", 1)[0] + "/" if index and index.canonical else None
    root_path = urlsplit(base).path if base else None

    for path, page in pages.items():
        name = path.relative_to(root.resolve()).as_posix()
        for repeated in sorted({i for i in page.ids if page.ids.count(i) > 1}):
            errors.append(f"{name}: the id {repeated} is used more than once")
        if not page.lang:
            errors.append(f"{name}: no language on <html>")
        if not page.title.strip():
            errors.append(f"{name}: no title")
        if not page.redirect:
            if page.h1 != 1:
                errors.append(f"{name}: {page.h1} first-level headings; a page has exactly one")
            if not (page.description or "").strip():
                errors.append(f"{name}: no description")
        for link in page.links:
            url = urlsplit(link)
            if url.scheme or url.netloc:
                if url.scheme not in {"https", "mailto"}:
                    errors.append(f"{name}: unsupported external link {link}")
                continue
            if url.path.startswith("/"):
                if not root_path or not url.path.startswith(root_path):
                    errors.append(f"{name}: link from the root of the host leaves the site: {link}")
                    continue
                target = (root / unquote(url.path[len(root_path):])).resolve()
            else:
                target = (path.parent / unquote(url.path)).resolve() if url.path else path
            if not target.is_relative_to(root.resolve()) or not target.is_file():
                errors.append(f"{name}: missing local target {link}")
            elif url.fragment and target.suffix == ".html" and unquote(url.fragment) not in pages[target].ids:
                errors.append(f"{name}: missing anchor {link}")

    sitemap = root / "sitemap.xml"
    if sitemap.is_file() and base:
        try:
            for loc in ElementTree.parse(sitemap).iter(SITEMAP):
                address = (loc.text or "").strip()
                if not address.startswith(base) or not (root / address[len(base):]).is_file():
                    errors.append(f"sitemap.xml: no page for {address}")
        except ElementTree.ParseError:
            pass  # reported above
    print(
        "\n".join(errors)
        if errors
        else f"Checked {len(pages)} pages: local links and assets valid; no inventory exports."
    )
    return int(bool(errors))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("site", type=Path)
    raise SystemExit(check(parser.parse_args().site))
