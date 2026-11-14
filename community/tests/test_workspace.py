"""The workspace of this repository: its records, its site and what it shares with sentier-bafu.

The scripts that check the records and build the site are copies of sentier-bafu's and are
tested there. These tests hold what is this repository's own: that its records pass, that its
site builds from them and passes the site check, that the site is recognisably this dataset's
(its index colour, its release, its words), and that it has no page, link or file of a served
release, because AGRIBALYSE is built on a licensed background and nothing built is published.
"""

import importlib.util
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import community  # noqa: E402
import shared_files  # noqa: E402

try:
    import build_site
    spec = importlib.util.spec_from_file_location("check_site", ROOT / "scripts/check_site.py")
    check_site = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check_site)
except ModuleNotFoundError:  # the markdown package is a site-build dependency only
    build_site = None

CONFIG = json.loads((ROOT / "site/config.json").read_text(encoding="utf-8"))
# The releases ADEME has published. A release is added to site/config.json, and here, only
# after ADEME has published it: nothing about an unpublished release belongs on the site.
PUBLISHED = {"3.2"}


class Quiet:
    def __enter__(self):
        self.real, sys.stdout = sys.stdout, io.StringIO()

    def __exit__(self, *_):
        sys.stdout = self.real


class Records(unittest.TestCase):
    def test_the_records_pass_the_check(self):
        errors, _, _ = community.problems(ROOT)
        self.assertEqual(errors, [])

    def test_the_shared_files_are_the_ones_named_in_the_manifest(self):
        self.assertEqual(shared_files.problems(ROOT), [])
        manifest = shared_files.read_manifest(ROOT)
        self.assertRegex(manifest["commit"], r"^[0-9a-f]{40}$")
        # what is this repository's own is not in the list of copies
        for own in ("site/config.json", "scripts/shared_files.py", "scripts/build_checks.py"):
            self.assertNotIn(own, manifest["files"])

    def test_only_published_releases_are_registered(self):
        registered = {release["id"] for release in CONFIG["releases"]}
        self.assertLessEqual(registered, PUBLISHED, "register a release only after ADEME has published it")
        for release in CONFIG["releases"]:
            self.assertTrue(release.get("background"), f'{release["id"]}: name the background it is built on')

    def test_a_finding_is_numbered_by_its_issue_and_names_no_dataset_by_number(self):
        config = community.load_config(ROOT)
        self.assertEqual(config["older_numbering_until"], 0)
        self.assertIsNone(config["dataset_code_pattern"])


class Forms(unittest.TestCase):
    def test_the_finding_form_has_the_headings_and_the_label_the_intake_reads(self):
        import intake
        form = (ROOT / intake.FORM_FILE).read_text(encoding="utf-8")
        self.assertTrue(intake.FORM_FILE.endswith(CONFIG["finding_form"]))
        labels = re.findall(r"^      label: (.+)$", form, re.M)
        known = {heading for _, heading, _ in intake.FORM}
        self.assertLessEqual(set(labels), known, "a heading the intake does not read")
        asked = {field for field, heading, _ in intake.FORM if heading in labels}
        # a process has a name and no number: the form has no field for dataset numbers
        self.assertEqual({field for field, _, required in intake.FORM if required} - asked, set())
        self.assertNotIn("datasets", asked)
        self.assertIn("scope", asked)
        self.assertIn(f'labels: ["{intake.FINDING_LABEL}", "needs-triage"]', form)
        self.assertEqual(intake.form_with_releases(form, community.load_config(ROOT)), form)

    def test_the_intake_workflow_starts_for_the_label_of_the_configuration(self):
        workflow = (ROOT / ".github/workflows/intake.yml").read_text(encoding="utf-8")
        self.assertIn(f"contains(github.event.issue.labels.*.name, '{CONFIG['finding_label']}')", workflow)

    def test_no_workflow_builds_or_publishes_a_release(self):
        workflows = sorted(path.name for path in (ROOT / ".github/workflows").glob("*.yml"))
        self.assertEqual(workflows, ["checks.yml", "ci.yml", "intake.yml", "pages.yml", "sync.yml"])
        for name in ("checks.yml", "pages.yml", "intake.yml", "sync.yml"):
            text = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
            for word in ("upload-release", "gh release", "softprops/action-gh-release", "ECOINVENT_"):
                self.assertNotIn(word, text, name)


class Intake(unittest.TestCase):
    """An issue filed with this repository's form, taken through the shared intake: the form
    has no field for dataset numbers, so the record must come out complete without one."""

    REPO = CONFIG["repository"]

    def issue(self, number=48, **changed):
        import intake
        answers = {
            "kind": "Defect: something in the data looks wrong (an amount, a unit, a link, a label)",
            "releases": "3.2",
            "scope": "A made-up process, 1 kg, FR",
            "observation": "A made-up amount of 10 kg where 1 kg is expected.",
            "method": "Read in a made-up export with a text editor.",
            "exposure": "_No response_",
            "notes": "_No response_",
        }
        answers.update(changed)
        form = (ROOT / intake.FORM_FILE).read_text(encoding="utf-8")
        asked = [(field, heading) for field, heading, _ in intake.FORM if f"label: {heading}" in form]
        body = "\n\n".join(f"### {heading}\n\n{answers[field]}" for field, heading in asked)
        return {"number": number, "title": "[Finding] A made-up amount ten times too high", "body": body,
                "created_at": "2026-11-02T09:00:00Z", "user": {"login": "reporter"},
                "html_url": f"{self.REPO}/issues/{number}"}

    def test_an_issue_filed_with_the_form_becomes_a_record_numbered_by_its_issue(self):
        import intake
        made = intake.record_from_issue(self.issue(), community.load_config(ROOT))
        self.assertEqual(made["result"], "record", made)
        record = made["record"]
        self.assertEqual((record["id"], record["issue"], record["releases"], record["datasets"]), ("F48", 48, ["3.2"], []))
        self.assertEqual(record["scope"], "A made-up process, 1 kg, FR")
        self.assertEqual(record["reported"]["url"], f"{self.REPO}/issues/48")
        self.assertEqual(community.stage(record), "filed")

    def test_an_issue_that_says_nothing_about_what_it_concerns_is_sent_back(self):
        import intake
        made = intake.record_from_issue(self.issue(scope="_No response_"), community.load_config(ROOT))
        self.assertEqual(made["result"], "incomplete", made)
        made = intake.record_from_issue(self.issue(releases="4.0"), community.load_config(ROOT))
        self.assertEqual(made["result"], "incomplete", "a release that is not registered is refused")

    def test_a_second_person_repeats_it_and_the_reporter_cannot(self):
        import intake
        record = intake.record_from_issue(self.issue(), community.load_config(ROOT))["record"]
        comment = {"id": 7, "created_at": "2026-11-05T10:00:00Z", "user": {"login": "second-person"},
                   "body": "/repeated reproduced\n\nI read 10 kg in the same place."}
        self.assertEqual(intake.command(comment["body"])[:2], ("repeated", "reproduced"))
        made = intake.second_measurement(record, comment, 48, self.REPO, "reproduced")
        self.assertEqual(made["result"], "repeated", made)
        self.assertEqual(community.stage(made["record"]), "confirmed")
        own = dict(comment, user={"login": "reporter"})
        self.assertEqual(intake.second_measurement(record, own, 48, self.REPO, "reproduced")["result"], "refused")


@unittest.skipIf(build_site is None, "the site build needs the markdown package")
class Site(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.temp.name) / "site"
        with Quiet():
            build_site.build(cls.out, offline=True, root=ROOT)
        cls.pages = {p.relative_to(cls.out).as_posix(): p.read_text(encoding="utf-8") for p in cls.out.rglob("*.html")}
        cls.framed = {name: text for name, text in cls.pages.items() if 'http-equiv="refresh"' not in text}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_the_site_passes_its_check(self):
        with Quiet():
            self.assertEqual(check_site.check(self.out), 0)
        for page in ("index.html", "findings.html", "feedback.html", "contributions.html", "build.html",
                     "take-part.html", "about/terms.html", "about/checks.html", "about/data.html",
                     "contributions/C001.html", "releases/3.2.html"):
            self.assertIn(page, self.pages)

    def test_every_page_carries_this_datasets_index_colour(self):
        # Aubergine, with the three shades made from it the way the brand's green family is made.
        # The same four are named in sentier-bafu's notes on the index colours of the sites.
        self.assertEqual(CONFIG["index"], {"color": "#5d4a66", "dark": "#46384d", "tint": "#e5dce9", "soft": "#a084ae"})
        colour, dark = CONFIG["index"]["color"], CONFIG["index"]["dark"]
        for name, text in self.framed.items():
            self.assertIn('<html lang="en" class="has-index">', text, name)
            self.assertIn(f"<style>:root{{--index:{colour};--index-dark:{dark};", text, name)
            self.assertIn(f'<meta name="theme-color" content="{colour}">', text, name)
        # the colour is not written into the stylesheet: that file is the same on every site
        self.assertEqual((self.out / "style.css").read_bytes(), (ROOT / "site/style.css").read_bytes())

    def test_no_page_file_or_link_of_a_served_release(self):
        self.assertNotIn("patched-release.html", self.pages)
        self.assertFalse((self.out / "api/v1/last-run.json").exists())
        for name, text in self.pages.items():
            self.assertNotIn("patched-release.html", text, name)
            self.assertNotIn("replay.js", text, name)
            self.assertNotIn("last-run.json", text, name)

    def test_the_release_page_names_the_background(self):
        self.assertIn("AGRIBALYSE 3.2 is built on ecoinvent 3.9.1.", self.pages["releases/3.2.html"])
        self.assertEqual(sorted(p.name for p in (self.out / "releases").glob("*.html")), ["3.2.html", "index.html"])

    def test_the_site_is_about_this_dataset_and_this_provider(self):
        home = self.pages["index.html"]
        self.assertIn("Feedback on ADEME", home)
        self.assertIn("issues/new?template=agribalyse-data-finding.yml", home)
        self.assertIn("Look up a finding number or a word", home)
        # The pages the build writes on its own name no other dataset, except in the footer's link
        # to the sibling site. Pages of prose may: they say where a lesson or a format comes from.
        prose = {"about/terms.html", "about/checks.html", "about/data.html", "contributions/C001.html"}
        sibling = re.compile(r'<a class="ext" href="https://sentier-dev\.github\.io/sentier-bafu/">[^<]*</a>')
        for name, text in self.framed.items():
            if name in prose:
                continue
            found = re.search(r".{0,60}bafu.{0,40}", sibling.sub("", text), re.I | re.S)
            self.assertIsNone(found, f"{name}: {found.group(0) if found else ''}")

    def test_old_addresses_lead_on(self):
        for old, new in CONFIG["redirects"].items():
            self.assertIn(old, self.pages)
            self.assertIn(new.rsplit("/", 1)[-1], self.pages[old], old)


if __name__ == "__main__":
    unittest.main()
