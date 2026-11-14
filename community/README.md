# The community workspace

This is the working space for people who use AGRIBALYSE. Users record what they find in the data, repeat each other's measurements and report the findings to ADEME, which publishes the database and decides what it changes. Proposals that go beyond a single finding are contributions, with their evidence and their checks.

The public site is built from the records here. Its pages say how to [take part](../site/take-part.md); this page says where things are in the repository.

| Where | What |
|---|---|
| `findings/<number // 1000>/F<number>.json` | one record per finding. A record holds what was observed and the dated evidence of what happened to it. Its status is computed from that evidence; nobody sets it by hand. The number of a finding is the number of its issue. |
| `contributions/C<number>.json` | one record per contribution; see [the contribution workflow](workflow.md) |
| `recommendations/tracker.json` | what was recommended to ADEME, and what ADEME answered |
| `templates/` | a template for each kind of record, for a run summary and for a build audit |
| [`build-validation.md`](build-validation.md), [`application-and-testing.md`](application-and-testing.md) | what the checks on a build cover, and how a contribution is applied and compared |
| [`lessons-from-bafu.md`](lessons-from-bafu.md) | engineering lessons from the BAFU/UVEK workspace and how they apply here |
| `tests/` | the tests of the records, the forms and the site |

```sh
python3 scripts/community.py check
python3 scripts/community.py compare release-summary.json changed-version-summary.json --out .local/comparisons/example.json
```

`check` validates every record and the references between them. A comparison needs the same build of ADEME's release and the same scope on both sides, and reports differences; it does not decide whether a change is right.

The scripts and the record schemas are shared with sentier-bafu; [site/README.md](../site/README.md) says which files, and how they are kept the same.

Nothing here implies ADEME's endorsement or an agreement among partners. Nothing is sent to ADEME automatically. Records are public: they hold no confidential discussion, no licensed export, no value of the ecoinvent background and nothing from a release that ADEME has not published.
