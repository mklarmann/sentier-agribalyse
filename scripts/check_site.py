"""Check generated public pages for local links, assets and inventory leakage."""

import argparse
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        for key in ("href", "src"):
            if key in attrs:
                self.links.append(attrs[key])


def check(root):
    pages = {}
    errors = []
    for path in root.rglob("*"):
        if path.suffix in {
            ".parquet",
            ".npz",
            ".bw2package",
            ".sqlite",
            ".db",
            ".csv",
            ".gz",
            ".zip",
        }:
            errors.append(f"Inventory or binary export must not enter site: {path.name}")
        if path.suffix == ".html":
            parser = Links()
            parser.feed(path.read_text())
            pages[path.resolve()] = parser
    if not pages or not (root / "index.html").is_file():
        errors.append("Site lacks index.html or pages")
    for path, parser in pages.items():
        for link in parser.links:
            url = urlsplit(link)
            if url.scheme or url.netloc:
                if url.scheme not in {"https", "mailto"}:
                    errors.append(f"{path.name}: unsupported external link {link}")
                continue
            target = (path.parent / unquote(url.path)).resolve() if url.path else path
            if not target.is_relative_to(root.resolve()) or not target.is_file():
                errors.append(f"{path.name}: missing local target {link}")
            elif (
                url.fragment
                and target.suffix == ".html"
                and unquote(url.fragment) not in pages[target].ids
            ):
                errors.append(f"{path.name}: missing anchor {link}")
    print(
        "\n".join(errors)
        if errors
        else f"Checked {len(pages)} pages: local links and assets valid; no inventory exports."
    )
    return int(bool(errors))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", type=Path)
    raise SystemExit(check(parser.parse_args().site))
