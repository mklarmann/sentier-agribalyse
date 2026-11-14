"""Build the public site from the records and an explicit, inventory-free file list.

Run: uv run --no-project --with markdown==3.7 scripts/build_site.py

The site has a page per finding, per contribution, per dataset a finding names and per
provider release, so it holds thousands of them. Issue details (comment counts, labels) come
from GitHub when it can be reached; see triage.py. The templates are in scripts/sitebuild/,
one function per component; this file reads the inputs, decides which pages exist and
writes them.

The build validates every record first, with the rules of `community.py check`, and writes
nothing while a record is invalid: what the check would refuse must not reach a page.
"""

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import community  # noqa: E402
import github_api  # noqa: E402
import last_run  # noqa: E402
import triage  # noqa: E402
from sitebuild import contributions, data, findings, lastrun, overview, pages, prose, shell, status, theme  # noqa: E402
from sitebuild.text import esc, plural  # noqa: E402,F401

ROOT = Path(__file__).resolve().parents[1]
RECORD_PAGES = {"community/findings": "findings", "community/contributions": "contributions"}
RECORD_FILE = re.compile(r"community/(findings|contributions)/(?:[^/]+/)*([FC][0-9]+)\.json")
# <!-- findings-list --> or <!-- generated: findings-list -->, alone in a paragraph or not.
MARKER = re.compile(r"<p>\s*<!--\s*(?:generated:\s*)?([a-z][a-z-]*)\s*-->\s*</p>|<!--\s*(?:generated:\s*)?([a-z][a-z-]*)\s*-->")
COUNT = re.compile(r"<!--\s*(?:generated:\s*)?count:([a-z:-]+)\s*-->")
# A block that opens its page: what precedes it and the block itself stand above the page's two
# columns, over the full width; "On this page" begins below it.
OPENING = {"last-run"}
# The blocks that show a release build. A site none of whose pages asks for one reads no run.
RUN_BLOCKS = re.compile(r"<!--\s*(?:generated:\s*)?(?:last-run|build-files)\s*-->")
OPENING_END = "<!-- end of the opening -->"
SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def revision(root):
    try:
        return subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        return None


def build_date():
    """Today, or the day SOURCE_DATE_EPOCH names: two builds of one revision are then identical."""
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        return datetime.datetime.fromtimestamp(int(epoch), datetime.timezone.utc).date().isoformat()
    return datetime.date.today().isoformat()


class Site:
    def __init__(self, out, source_repository=None, source_ref=None, preview_url=None,
                 issues_snapshot=None, offline=False, require_issues=False, root=ROOT,
                 last_run_snapshot=None, built_by=None):
        self.out = Path(out)
        self.root = Path(root)
        # A record that `community.py check` refuses must not be built into a page either.
        errors, _, _ = community.problems(self.root)
        if errors:
            raise SystemExit("The records are not valid; nothing was built.\n" + "\n".join(errors))
        self.config = json.loads((self.root / "site/config.json").read_text())
        # The index colour of this dataset's site, checked; None while the site sets none.
        self.theme = theme.read(self.config)
        self.repo = self.config["repository"]
        self.source_repo = source_repository or self.repo
        self.ref = source_ref or self.config["source_ref"]
        if preview_url and not preview_url.startswith("https://github.com/"):
            raise ValueError("Preview notice must link to a GitHub pull request")
        self.preview_url = preview_url
        # `built_by` is the repository whose workflow builds this copy ("owner/name"). When it is
        # not the repository the site belongs to, every page says that it is a copy built elsewhere.
        own = github_api.repository_slug(self.repo)
        if built_by and not github_api.REPOSITORY.fullmatch(built_by):
            raise ValueError("--built-by names a repository as owner/name")
        self.built_by = built_by or own
        self.elsewhere = self.built_by != own
        self.dataset = self.config["dataset"]
        self.provider = self.config["provider"]
        self.root_path = urlsplit(self.config["site_url"]).path.rstrip("/") + "/"
        self.records_config = community.load_config(self.root)
        self.docs = self.config["documents"]
        # What differs from one dataset's site to another's (see site/README.md, "A sibling site").
        self.code_pattern = self.records_config["dataset_code_pattern"]
        self.lookup_example = self.records_config["lookup_example"]
        self.finding_form = self.records_config["finding_form"]
        # The page of the patched copy, where this site has one ("patched_page" in the
        # configuration names it): other pages lead to it.
        self.patched_page = self.config.get("patched_page")
        if self.patched_page is not None and self.patched_page not in {doc["page"] for doc in self.docs}:
            raise ValueError(f'site/config.json: "patched_page" is {self.patched_page}, which is no page of "documents"')
        # Where a link to a source file leads on the site: the page built from it.
        self.routes = {"community/findings/README.md": "findings.html"}
        for doc in self.docs:
            for source in [doc["source"]] + doc.get("also", []):
                self.routes[source] = doc["page"]
        for cid, sources in self.config.get("assessments", {}).items():
            for source in sources:
                self.routes.setdefault(source, f"contributions/{cid}.html")
        self.findings = community.load_findings(self.root)
        self.contributions = community.load_contributions(self.root)
        self.patches = community.load_patches(self.root)
        issues, self.issues_source = triage.load_issues(
            self.repo, issues_snapshot, offline, require_issues
        )
        self.triage = triage.assemble(self.findings, self.repo, issues, self.patches)
        # The last run of the workflow that site/config.json names under "run", read from the
        # runs of the repository that builds this site: only for a site that has a page for it.
        shows_run = any(
            RUN_BLOCKS.search((self.root / source).read_text())
            for doc in self.docs for source in [doc["source"], *doc.get("also", [])]
            if (self.root / source).is_file()
        )
        self.run = last_run.settings(self.config)
        self.last_run = self.run_reader = None
        if shows_run:
            if self.run is None:
                raise ValueError('a page shows the last run, and site/config.json has no "run" that says which workflow')
            self.run_reader = last_run
            self.last_run = last_run.load(self.built_by, self.run, last_run_snapshot, offline)
        self.built = build_date()
        self.revision = revision(self.root)
        self.written = set()
        self.pages = {}        # page -> date of its last change, for the sitemap
        self.site_links = {}   # links from prose to a file of the built site -> the source that asks

    # ------------------------------------------------------------- derived views

    @property
    def triage(self):
        return self._triage

    @triage.setter
    def triage(self, value):
        self._triage, self._derived = value, {}

    def derived(self, name, make):
        if name not in self._derived:
            self._derived[name] = make()
        return self._derived[name]

    @property
    def by_id(self):
        return self.derived("by_id", lambda: {f["id"]: f for f in self.triage["findings"]})

    @property
    def changes(self):
        """Every dated step of every finding, newest first."""
        return self.derived("changes", lambda: community.changes(self.triage["findings"]))

    @property
    def datasets(self):
        return self.derived("datasets", lambda: community.dataset_index(self.triage["findings"], self.patches))

    @property
    def releases(self):
        return self.derived("releases", lambda: community.release_index(self.triage["findings"], self.records_config))

    # ------------------------------------------------------------------ helpers

    def label(self, stage):
        return community.status_label(stage, self.provider)

    def release_name(self, rid):
        names = {r["id"]: r["name"] for r in self.records_config["releases"]}
        return names.get(rid, rid)

    def target(self, link, source):
        """Where a relative link in a source file points on the site (or on GitHub)."""
        path, sep, fragment = link.partition("#")
        absolute = (self.root / Path(source).parent / path).resolve()
        try:
            relative = absolute.relative_to(self.root.resolve()).as_posix()
        except ValueError:
            raise ValueError(f"Link leaves repository: {link}") from None
        page = self.routes.get(relative)
        record = RECORD_FILE.fullmatch(relative)
        if not page and record:
            # A link to a record names the file's real path, so it also works on GitHub.
            if not absolute.is_file():
                raise ValueError(f"{source} links to a record that is not there: {link}")
            page = f"{record.group(1)}/{record.group(2)}.html"
        if not page and relative in RECORD_PAGES:
            page = f"{RECORD_PAGES[relative]}.html"
        if not page and relative.startswith("site/") and not absolute.exists():
            # No file of the repository: a file of the built site, named from its root
            # (site/feed.xml, site/api/v1/findings.json, site/changes.html). Checked after the build.
            page = relative[len("site/"):]
            self.site_links.setdefault(page, source)
        if page:
            return page + (sep + fragment if sep else ""), True
        return f"{self.source_repo}/blob/{self.ref}/{relative}" + (sep + fragment if sep else ""), False

    def render(self, text, source, up="", shift=0):
        """Markdown of a prose source to (html, sections); see sitebuild/prose.py."""
        return prose.render(self, text, source, up, shift)

    def record_text(self, text, inline=False, **options):
        """Markdown of a record; see sitebuild/prose.py."""
        return prose.record_text(self, text, inline, **options)

    def shell(self, title, body, current, **options):
        return shell.shell(self, title, body, current, **options)

    # ------------------------------------------------------------------ writing

    def write(self, page, text):
        """Write one file of the site. A path that leaves the output folder is refused."""
        path = self.out / page
        if not path.resolve().is_relative_to(self.out.resolve()):
            raise ValueError(f"Refusing to write outside the output folder: {page}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        self.written.add(path)

    def page(self, page, text, changed=None):
        """Write a page that belongs in the sitemap."""
        self.write(page, text)
        self.pages[page] = changed

    def copy(self, source, page):
        path = self.out / page
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, path)
        self.written.add(path)

    def write_json(self, page, data, one_per_line=None):
        """JSON for tools. A list that grows with the records is written one entry per line:
        a third of the size of an indented file, and still readable and comparable."""
        if one_per_line is None:
            self.write(page, json.dumps(data, indent=1, ensure_ascii=False) + "\n")
            return
        entries = data[one_per_line]
        compact = lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":"))  # noqa: E731
        if isinstance(entries, dict):
            body = ",\n".join(f"{json.dumps(key)}:{compact(value)}" for key, value in entries.items())
            body = "{\n" + body + "\n}"
        else:
            body = "[\n" + ",\n".join(compact(value) for value in entries) + "\n]"
        head = json.dumps({k: v for k, v in data.items() if k != one_per_line}, indent=1, ensure_ascii=False)
        self.write(page, head[: head.rindex("}")].rstrip() + f',\n "{one_per_line}": {body}\n}}\n')

    # ---------------------------------------------------------------- templates

    def findings_list(self, up=""):
        return findings.findings_list(self, up)

    def finding_page(self, f):
        return findings.finding_page(self, f)

    def contributions_list(self, up=""):
        return contributions.contributions_list(self, up)

    def contribution_page(self, c):
        return contributions.contribution_page(self, c)

    def overview(self):
        return overview.overview(self)

    # -------------------------------------------------------------- prose pages

    def blocks(self, up=""):
        """What a prose page can ask for with a marker, <!-- name -->; listed in site/README.md.
        (function, takes the full width of the page)."""
        return {
            "findings-list": (lambda: findings.findings_list(self, up), True),
            "contributions-list": (lambda: contributions.contributions_list(self, up), True),
            "feedback-lists": (lambda: pages.feedback_lists(self, up), True),
            "status-tracker": (lambda: status.path_with_counts(self, up), True),
            "status-vocabulary": (lambda: status.vocabulary(self), False),
            "second-measurement-list": (lambda: overview.second_measurement_list(self, up), False),
            "recent-changes": (lambda: pages.change_lines(self, self.changes[:5], up), False),
            "patch-table": (lambda: pages.patch_table(self, up), False),
            "last-run": (lambda: lastrun.last_run(self, up), False),
            "build-files": (lambda: lastrun.packages(self, up), False),
            "data-files": (lambda: pages.data_files(self, up), False),
            "lookup": (lambda: shell.lookup(self, up), False),
        }

    def counts(self):
        """The numbers a prose page can ask for with <!-- count:name -->, so none is typed by hand."""
        listed = (self.patches or {}).get("patches", [])
        numbers = {
            "findings": len(self.triage["findings"]),
            "contributions": len(self.contributions),
            "patches": len(listed),
            "patches-with-finding": sum(1 for x in listed if x["findings"]),
            "patches-without-finding": sum(1 for x in listed if not x["findings"]),
            "findings-with-patch": sum(1 for f in self.triage["findings"] if f["patches"]),
            "datasets": len(self.datasets),
            "releases": len(self.records_config["releases"]),
        }
        for s in community.STATUSES:
            numbers[f'status:{s["key"]}'] = self.triage["counts"].get(s["key"], 0)
        return numbers

    def document(self, doc):
        """One prose page: counts filled in, Markdown rendered, generated blocks put in place."""
        source, up = doc["source"], "../" * doc["page"].count("/")
        numbers = self.counts()

        def count(match):
            if match.group(1) not in numbers:
                raise ValueError(f"{source} asks for a count the build does not know: {match.group(1)}")
            return f"{numbers[match.group(1)]:,}"

        text = COUNT.sub(count, (self.root / source).read_text())
        rendered, sections = self.render(text, source, up)
        blocks, wide, used = self.blocks(up), False, set()

        def block(match):
            nonlocal wide
            name = match.group(1) or match.group(2)
            if name not in blocks:
                return match.group(0)
            make, full = blocks[name]
            wide = wide or full
            used.add(name)
            return make() + (OPENING_END if name in OPENING else "")

        rendered = MARKER.sub(block, rendered)
        opening = ""
        if OPENING_END in rendered:
            opening, rendered = rendered.split(OPENING_END, 1)
        # The packages of a release are also offered beside the text, under "On this page".
        beside = lastrun.rail_box(self, up) if "build-files" in used else ""
        return shell.prose_page(self, doc, rendered, sections, listing=wide, up=up, opening=opening, beside=beside)

    # --------------------------------------------------------------------- build

    def titles(self):
        """What each page is called, for the text of a redirect."""
        names = {page: label for page, label in self.config["nav"] + self.config["footer"]}
        names.update({doc["page"]: doc["title"] for doc in self.docs})
        names.update({f'contributions/{c["id"]}.html': f'contribution {c["id"]}' for c in self.contributions})
        return names

    def build(self):
        out = self.out
        # status.json marks a folder this build wrote before; only there may files be removed.
        rebuilt = (out / "status.json").exists()
        self.written, self.pages, self.site_links = set(), {}, {}
        out.mkdir(parents=True, exist_ok=True)
        for asset in sorted((self.root / "site/assets").iterdir()):
            if asset.is_file():
                self.copy(asset, f"assets/{asset.name}")
        self.copy(self.root / "site/style.css", "style.css")
        (out / ".nojekyll").touch()

        self.page("index.html", self.overview())
        for doc in self.docs:
            self.page(doc["page"], self.document(doc))
        for f in self.triage["findings"]:
            self.page(f'findings/{f["id"]}.html', self.finding_page(f), f["changed"])
        self.write_json("findings/index.json", findings.list_index(self), one_per_line="rows")
        for c in self.contributions:
            self.page(f'contributions/{c["id"]}.html', self.contribution_page(c))
        for code, entry in self.datasets.items():
            self.page(f"datasets/{int(code)}.html", pages.dataset_page(self, int(code), entry))
        for rid, entry in self.releases.items():
            if not SAFE_NAME.fullmatch(rid):
                raise ValueError(f"site/config.json: a release id cannot be a page name: {rid!r}")
            self.page(f"releases/{rid}.html", pages.release_page(self, rid, entry))
        for batch, entry in pages.batches(self).items():
            if not SAFE_NAME.fullmatch(batch):
                raise ValueError(f"A batch id cannot be a page name: {batch!r}")
            self.page(f"feedback/{batch}.html", pages.batch_page(self, batch, entry), entry["date"])
        self.page("changes.html", pages.changes_page(self), self.changes[0]["date"] if self.changes else None)
        self.page("housekeeping.html", pages.housekeeping(self))
        self.write("feed.xml", pages.feed(self))

        titles = self.titles()
        for old, new in self.config.get("redirects", {}).items():
            if old in self.pages:
                raise ValueError(f"site/config.json redirects {old}, which is a page of the site")
            self.write(old, shell.redirect(self, new, titles.get(new, new), "../" * old.count("/")))
        # GitHub Pages serves 404.html for any missing address, so its links start at the root.
        self.write("404.html", shell.not_found(self))
        data.write_data(self)
        if self.last_run is not None:
            self.write_json("api/v1/last-run.json", lastrun.public_record(self.last_run))
        self.write("sitemap.xml", pages.sitemap(self))

        for page, source in self.site_links.items():
            if not (out / page).is_file() or (out / page) not in self.written:
                raise ValueError(f"{source} links to {page}, which the site does not have")
        if rebuilt:
            # A file of an earlier build that this one no longer writes would stay reachable.
            for stale in sorted(p for p in out.rglob("*") if p.is_file() and p not in self.written and p.name != ".nojekyll"):
                stale.unlink()
            for folder in sorted((p for p in out.rglob("*") if p.is_dir()), reverse=True):
                if not any(folder.iterdir()):
                    folder.rmdir()
        print(f"Built {self.dataset}: {len(self.pages)} pages in {out}")
        if self.last_run is not None:
            print(self.run_reader.said(self.last_run))
        # For maintainers, in the build log only: a public page does not name labels.
        differences = self.triage["label_differences"]
        if differences:
            print(f"Labels of {plural(len(differences), 'issue')} differ from the records:")
            for d in differences:
                change = "; ".join(
                    part for part in (
                        "add " + ", ".join(d["add"]) if d["add"] else "",
                        "remove " + ", ".join(d["remove"]) if d["remove"] else "",
                    ) if part
                )
                print(f"  #{d['issue']} ({', '.join(d['findings'])}): {change}")


def build(out, source_repository=None, source_ref=None, preview_url=None, issues_snapshot=None,
          offline=False, require_issues=False, root=ROOT, last_run_snapshot=None, built_by=None):
    Site(out, source_repository, source_ref, preview_url, issues_snapshot, offline, require_issues, root,
         last_run_snapshot, built_by).build()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "_site")
    parser.add_argument("--source-repository", help="Repository containing this build's source")
    parser.add_argument("--source-ref", help="Source branch or revision for repository links")
    parser.add_argument("--preview-url", help="Show a review notice linking to this pull request")
    parser.add_argument("--issues", type=Path, help="Issue snapshot (JSON) instead of reading GitHub")
    parser.add_argument("--offline", action="store_true", help="Do not read issues from GitHub")
    parser.add_argument("--require-issues", action="store_true", help="Fail when GitHub cannot be read")
    parser.add_argument("--last-run", type=Path, help="Record of the last build (JSON) instead of reading GitHub")
    parser.add_argument("--built-by", metavar="OWNER/NAME",
                        help="The repository whose workflow builds this copy: its builds are shown, "
                             "and a copy built by another repository than the site's own says so on every page")
    args = parser.parse_args()
    build(args.out, args.source_repository, args.source_ref, args.preview_url, args.issues,
          args.offline, args.require_issues, last_run_snapshot=args.last_run, built_by=args.built_by)
