# Data (JSON)

The findings, the contributions and their statuses are also published as JSON files, for tools and for other projects. The files hold what the site shows: the text of the records, statuses, dates and links. They hold no inventory files.

Addresses are relative to `https://sentier-dev.github.io/sentier-agribalyse/`. Inside `api/v1/` a field is never renamed or removed, and fields may be added. A change that would break a reader gets a new folder, `api/v2/`, beside the old one.

<!-- generated: data-files -->

The two files under `schema/` are the JSON Schema of a finding record and of a contribution record. They are the rules that the records in the repository are checked against.

The files have the same shape on every Sentier dataset site, so a tool that reads one site reads the others. For that reason the `schema` value inside a file names the format, `sentier-bafu/findings/1` and so on, also on this site. It does not say that the content is about BAFU's data.

AGRIBALYSE processes have a name and a process identifier of letters and digits, and no number, so `api/v1/datasets.json` is empty here. A finding says in its `scope` what it is about, for a single process with its process identifier.
