# Data (JSON)

The findings, the contributions and their statuses are also published as JSON files, for tools and for other projects. The files hold what the site shows: the text of the records, statuses, dates and links. They hold no inventory files.

Addresses are relative to `https://sentier-dev.github.io/sentier-agribalyse/`. Inside `api/v1/` a field is never renamed or removed, and fields may be added. A change that would break a reader gets a new folder, `api/v2/`, beside the old one.

| File | What it holds |
|---|---|
| [`api/v1/findings.json`](api/v1/findings.json) | The status vocabulary and one entry per finding: number, title, kind, status, releases, the date of each step. |
| `api/v1/findings/F<number>.json` | One file per finding: the full record and what is derived from it. |
| [`api/v1/contributions.json`](api/v1/contributions.json) | The kinds of contribution and one entry per contribution. |
| [`api/v1/status.json`](api/v1/status.json) | The number of findings by status and the identity of the build. |
| [`schema/finding.schema.json`](schema/finding.schema.json) | The JSON Schema of a finding record. |
| [`schema/contribution.schema.json`](schema/contribution.schema.json) | The JSON Schema of a contribution record. |
| [`ledger.md`](ledger.md) | The findings as one table, one line each, in Markdown. |
| [`feed.xml`](feed.xml) | What changed, as an Atom feed. |
| [`sitemap.xml`](sitemap.xml) | Every page of the site. |

The two files under `schema/` are the JSON Schema of a finding record and of a contribution record. They are the rules that the records in the repository are checked against.

The files have the same shape on every Sentier dataset site, so a tool that reads one site reads the others. For that reason the `schema` value inside a file names the format, `sentier-bafu/findings/1` and so on, also on this site. It does not say that the content is about BAFU's data.

AGRIBALYSE processes have a name and no number, so `api/v1/datasets.json` is empty here. A finding says in its `scope` what it is about.
