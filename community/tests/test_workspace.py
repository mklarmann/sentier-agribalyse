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
import shutil
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
        for own in ("site/config.json", "site/licensed-run.json", "scripts/build_checks.py"):
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

    def test_site_workflows_use_only_the_public_run_record(self):
        workflows = sorted(path.name for path in (ROOT / ".github/workflows").glob("*.yml"))
        # ci.yml is the import's own. Intake and Sync, which write to issues, are not here yet.
        self.assertEqual(workflows, ["checks.yml", "ci.yml", "import-run.yml", "pages.yml"])
        for name in ("checks.yml", "import-run.yml", "pages.yml"):
            text = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
            for word in ("upload-release", "gh release", "softprops/action-gh-release", "ECOINVENT_", "uv sync", "dds-",
                         "issues: write", "pull-requests: write", "contents: write"):
                self.assertNotIn(word, text, name)
            if name in ("pages.yml", "checks.yml"):
                self.assertIn("--last-run site/licensed-run.json", text, name)


class ImportRun(unittest.TestCase):
    """The run the page "Import and build" shows: one stage for real, five named as not run here."""

    @classmethod
    def setUpClass(cls):
        import import_run
        cls.module = import_run
        with Quiet():
            cls.account = import_run.run(ROOT)

    def test_the_first_stage_reads_the_shipped_export_and_agrees_with_its_manifest(self):
        from runrecord import summary
        self.assertEqual(summary.shape_errors(self.account), [])
        self.assertEqual(self.account["status"], "completed")
        first = self.account["steps"][0]
        self.assertEqual((first["name"], first["status"]), ("ADEME's export", "completed"))
        manifest = json.loads((ROOT / self.module.MANIFEST).read_text(encoding="utf-8"))
        figures = {figure["label"]: figure["value"] for figure in first["figures"]}
        self.assertEqual(figures["processes"], int(manifest["processes"]["kept"]))
        self.assertEqual(figures["ecoinvent datasets taken out"], int(manifest["processes"]["removed"]))
        self.assertEqual(figures["bytes shipped"], (ROOT / self.module.EXPORT).stat().st_size)

    def test_the_stages_that_need_a_licence_are_not_run_and_say_why(self):
        later = self.account["steps"][1:]
        self.assertEqual([step["name"] for step in later], list(self.module.LICENSED))
        for step in later:
            self.assertEqual(step["status"], "not run here", step["name"])
            self.assertIn("ecoinvent 3.9.1 licence", step["reason"])
            self.assertEqual(step["figures"], [])
        # the run reads nothing a licence gives, and no command of the licensed pipeline
        source = (ROOT / "scripts/import_run.py").read_text(encoding="utf-8")
        for word in ("ecoinvent-3.9.1", "subprocess", "dds-", "registry/"):
            self.assertNotIn(word, source)

    def test_an_export_that_is_not_the_recorded_file_fails_the_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "source").mkdir()
            manifest = json.loads((ROOT / self.module.MANIFEST).read_text(encoding="utf-8"))
            manifest["stripped_csv"]["sha256"] = "0" * 64
            (root / self.module.MANIFEST).write_text(json.dumps(manifest))
            (root / self.module.EXPORT).write_bytes((ROOT / self.module.EXPORT).read_bytes())
            with Quiet():
                account = self.module.run(root)
        self.assertEqual(account["status"], "failed")
        self.assertEqual(account["steps"][0]["status"], "failed")
        self.assertIn("checksums differ", account["steps"][0]["reason"])
        self.assertTrue(account["blocking"])

    def test_every_stage_has_its_words_and_the_site_names_the_workflow_that_runs_it(self):
        words = json.loads((ROOT / "site/run-steps.json").read_text(encoding="utf-8"))["steps"]
        self.assertEqual(list(words), [step["name"] for step in self.account["steps"]])
        run = CONFIG["run"]
        workflow = (ROOT / ".github/workflows" / run["workflow"]).read_text(encoding="utf-8")
        self.assertIn(f'name: {run["artifact"]}', workflow)
        self.assertIn("scripts/import_run.py --out", workflow)
        self.assertIn("<!-- generated: last-run -->", (ROOT / "site/build.md").read_text(encoding="utf-8"))


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
    def test_a_process_identifier_given_with_the_finding_is_what_the_list_searches(self):
        """The shared record format lists datasets by number, and an AGRIBALYSE process has an
        identifier of letters and digits. The form asks for it in what the finding concerns.
        It must then be in the text that the findings list searches (site/assets/list.js: the
        number, the title and the two texts of what a finding concerns) and on the finding's page."""
        import intake
        identifier = "MADEUPID000000000000048"
        self.assertIn("process identifier", (ROOT / intake.FORM_FILE).read_text(encoding="utf-8"))
        made = intake.record_from_issue(
            self.issue(scope=f"A made-up process, 1 kg, FR; process identifier {identifier}"),
            community.load_config(ROOT))
        self.assertEqual(made["result"], "record", made)
        with tempfile.TemporaryDirectory() as tmp:
            root, out = Path(tmp) / "tree", Path(tmp) / "site"
            shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(
                ".git", ".venv", ".local", "_site", "source", "tests", "__pycache__"))
            record = root / community.record_path(made["record"])
            record.parent.mkdir(parents=True, exist_ok=True)
            record.write_text(json.dumps(made["record"], indent=1) + "\n", encoding="utf-8")
            self.assertEqual(community.problems(root)[0], [])
            with Quiet():
                build_site.build(out, offline=True, root=root)
            rows = json.loads((out / "findings/index.json").read_text(encoding="utf-8"))["rows"]
            row = next(r for r in rows if r[0] == 48)
            self.assertIn(identifier, f"{row[2]} {row[3]}")
            self.assertIn(identifier, (out / "findings/F48.html").read_text(encoding="utf-8"))


@unittest.skipIf(build_site is None, "the site build needs the markdown package")
class Site(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.temp.name) / "site"
        with Quiet():
            build_site.build(cls.out, offline=True, root=ROOT, last_run_snapshot=ROOT / "site/licensed-run.json")
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

    def test_feedback_and_contributions_stay_in_their_review_sections(self):
        labels = ["Overview", "AGRIBALYSE catalogue", "Sources", "Cases", "Build", "Contribute"]
        for page, html in self.framed.items():
            with self.subTest(page=page):
                nav = re.search(r'<nav class="nav".*?</nav>', html, re.S)[0]
                self.assertEqual(re.findall(r'<a [^>]*>([^<]*)</a>', nav), labels)
                self.assertEqual(nav.count("aria-current"), 0 if page == "404.html" else 1)
        for page, parent, view in (
            ("feedback.html", "Cases", "Feedback to ADEME"),
            ("cases/F7.html", "Cases", "Case register"),
            ("findings/F7.html", "Cases", "Findings"),
            ("earlier-reports.html", "Sources", "Earlier reports"),
            ("contributions/C001.html", "Cases", "Proposed changes"),
            ("about/terms.html", "Sources", "Access and terms"),
            ("about/data.html", "Sources", "Public records"),
            ("housekeeping.html", "Contribute", "Maintainer checks"),
        ):
            with self.subTest(page=page):
                html = self.pages[page]
                main = re.search(r'<nav class="nav".*?</nav>', html, re.S)[0]
                views = re.search(r'<nav class="subnav".*?</nav>', html, re.S)[0]
                self.assertIn(f'aria-current="page">{parent}</a>', main)
                self.assertNotIn("Feedback to ADEME", main)
                self.assertRegex(views, rf'aria-current="(?:page|location)">{view}</a>')

    def test_the_flow_list_case_links_to_its_original_evidence(self):
        sources = json.loads((self.out / "api/v1/sources.json").read_text())["sources"]
        cases = json.loads((self.out / "api/v1/cases.json").read_text())["cases"]
        flow_case = next(case for case in cases if case["id"] == "F7")
        linked = {s["id"]: s["url"] for s in sources if "F7" in s["cases"]}
        self.assertEqual(set(linked), set(flow_case["sources"]))
        self.assertEqual(linked["report-F7"], CONFIG["repository"] + "/issues/7")
        self.assertEqual(linked["flow-download"], CONFIG["repository"] + "/pull/9")

    def test_comparison_picker_uses_the_case_register_and_keeps_the_recorded_diagnostics(self):
        html = self.pages["before-after.html"]
        register = json.loads((self.out / "api/v1/cases.json").read_text())["cases"]
        picker = re.findall(r'<select\b[^>]*\bid="review-case"[^>]*>(.*?)</select>', html, re.S)
        self.assertEqual(len(picker), 1)
        options = re.findall(r'<option\b[^>]*\bvalue="([^"]*)"', picker[0])
        self.assertEqual(options[0], "")
        self.assertCountEqual(options[1:], [case["id"] for case in register])
        payload = re.search(r'<script[^>]*data-sd="data"[^>]*>(.*?)</script>', html, re.S)
        diagnostics = json.loads(payload[1])
        record = json.loads((ROOT / "site/licensed-run.json").read_text())
        self.assertEqual(diagnostics, record["diagnostics"])

    def test_water_study_links_the_source_control_to_its_build_step(self):
        html = self.pages["before-after.html"]
        self.assertEqual(html.count('id="water-use-gap"'), 1)
        self.assertIn('href="#sd.step=water"', html)
        self.assertIn('id="sd.step=water"', html)
        self.assertIn("all 2,451 foods fall within 5%", html)
        self.assertIn("210 processes", html)
        run = json.loads((self.out / "api/v1/last-run.json").read_text())
        water = next(step for step in run["diagnostics"]["steps"] if step["id"] == "water")
        self.assertTrue(water["link"].endswith("/before-after.html#water-use-gap"))

    def test_published_reference_covers_the_catalogue_and_uses_the_step_indicator_ids(self):
        ref = json.loads((self.out / "assets/ademe-reference.json").read_text())
        catalogue = json.loads((self.out / "assets/agribalyse-catalogue.json").read_text())
        run = json.loads((ROOT / "site/licensed-run.json").read_text())["diagnostics"]
        self.assertEqual(ref["source"], "https://data.ademe.fr/data-fair/api/v1/datasets/agribalyse-31-synthese")
        self.assertEqual(set(ref["scores"]), {food[2] for food in catalogue["foods"]})
        ids = [i["id"] for i in ref["indicators"]]
        self.assertEqual(ids, [i["id"] for i in run["indicators"]])
        self.assertTrue(all(i["unit"] for i in ref["indicators"]))
        self.assertTrue(all(len(row) == len(ids) for row in ref["scores"].values()))
        self.assertIn('href="browse.html?kind=results"', self.pages["before-after.html"])
        self.assertFalse((self.out / "matrix.js").exists())

    def test_no_page_file_or_link_of_a_served_release(self):
        self.assertNotIn("patched-release.html", self.pages)
        # This review records a licensed run completed outside GitHub.
        record = json.loads((self.out / "api/v1/last-run.json").read_text(encoding="utf-8"))
        self.assertIsNone(record.get("run"))
        self.assertIsNotNone(record.get("local"))
        self.assertEqual([s["name"] for s in record["summary"]["steps"]], ["ADEME's export", "Licensed files", "Registry", "Link", "Score", "Export"])
        diagnostics = record["diagnostics"]
        self.assertEqual((diagnostics["audience"], diagnostics["tier"]), ("public", "items"))
        html = self.pages["before-after.html"]
        matrix = json.loads((self.out / "assets/food-scores.json").read_text())
        self.assertIn('data-sd-matrix="food-scores.json"', html)
        self.assertEqual(matrix["of"]["states"], [s["id"] for s in diagnostics["states"]])
        self.assertEqual(matrix["of"]["states"][::5], ["ademe", "integrated"])
        self.assertEqual(len(matrix["of"]["indicators"]), 19)
        self.assertEqual(len(matrix["items"]), diagnostics["items_count"]["all"])
        self.assertEqual(len({row[0] for row in matrix["items"]}), 2451)
        self.assertTrue(all(len(row) == 6 * 19 for row in matrix["values"]))
        for name, text in self.pages.items():
            self.assertNotIn("patched-release.html", text, name)
            if name not in ("build.html", "about/data.html", "runs.html"):
                self.assertNotIn("replay.js", text, name)
                self.assertNotIn("last-run.json", text, name)

    def test_the_release_page_names_the_background(self):
        self.assertIn("AGRIBALYSE 3.2 is built on ecoinvent 3.9.1.", self.pages["releases/3.2.html"])
        self.assertEqual(sorted(p.name for p in (self.out / "releases").glob("*.html")), ["3.2.html", "index.html"])

    def test_the_site_is_about_this_dataset_and_this_provider(self):
        home = self.pages["index.html"]
        self.assertIn("Feedback on AGRIBALYSE data, from the people who use it", home)
        submission = CONFIG["finding_submission_url"].replace("&", "&amp;")
        hero_actions = re.search(r'<div class="actions">(.*?)</div>', home, re.S)[1]
        self.assertIn(f'href="{submission}"', hero_actions)
        self.assertIn('href="cases.html"', hero_actions)
        self.assertIn(f'href="{submission}"', self.pages["take-part.html"])
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
