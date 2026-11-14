# Take part

You can repeat a measurement, report a finding or propose a contribution. Reports and comments are written on GitHub, in public. Reading needs no account. Writing needs a free GitHub account.

## Repeat a measurement

This is the most useful help. Before a finding is reported to ADEME, a second person is asked to repeat the measurement. The findings below still need a second measurement.

<!-- generated: second-measurement-list -->

1. Choose a finding with the status "Needs a second measurement", from the list above or from the [findings](findings.md) list. Its page says what was observed and links to the place where the finding is discussed. This is usually a GitHub issue.
2. Repeat the measurement on ADEME's release files, as you received them. Do not measure on a database that the files were imported into: an import can change the data.
3. Write what you got as a comment in that discussion: the value with its unit, the file and the release you looked at, and how you got the value. A different result is as useful as the same one.
4. A maintainer then adds your second measurement to the finding's record. The record is public. It holds your GitHub user name, the date and a link to your comment.

The second measurement must come from someone other than the person who reported the finding. Some measurements need a script. For others a text editor is enough: you open ADEME's export and read a value.

## Report a finding

You measured something in ADEME's data that looks wrong, or that you cannot explain.

1. [Open a finding](https://github.com/sentier-dev/sentier-agribalyse/issues/new?template=agribalyse-data-finding.yml) and fill in the form: the release, the process or group of processes (for a single process with its process identifier from ADEME's export), where you looked, what you measured and how, and why it looks wrong. Give numbers with their units.
2. A maintainer reads the report and adds a record. The finding gets a number, which is the number of its issue with an F in front.
3. The finding has the status "Needs a second measurement" until a second person has repeated it.
4. Then the finding is reported to ADEME. ADEME decides what it changes. ADEME's answer is recorded. The finding is resolved once an AGRIBALYSE release covers the point.

A finding that does not hold when it is measured again stays listed as "Withdrawn", so that nobody reports it a second time.

Something the import does wrong is not a finding about ADEME's data. Report it as an ordinary issue in the repository.

## Propose a contribution

A contribution is a mapping, a model, a parameter scenario or a method variant. [Open a contribution](https://github.com/sentier-dev/sentier-agribalyse/issues/new?template=community-contribution.yml) and describe what you propose and the evidence for it. The [contributions](contributions.md) page explains the kinds of contribution, the steps and what review means.

Not sure where something belongs? [Start a discussion](https://github.com/sentier-dev/sentier-agribalyse/issues/new?template=discussion.yml).

## Ground rules

- Measure on ADEME's release files. Say what you measured and what you did not.
- Quote process names and single values of AGRIBALYSE. Never paste values of the ecoinvent background: they are licensed data.
- Share nothing confidential: no licensed exports, no private correspondence, nothing from a release that ADEME has not published.
- People review and decide. Work done with an AI agent says so.
- Nothing here implies ADEME's endorsement.
