# Findings

A finding is a measured observation about ADEME's data: an amount that looks wrong, an input that leads nowhere, a unit that does not fit. Each finding has a number, a record of what was observed, and a public place where it is discussed.

Findings are feedback to ADEME, the French Agency for Ecological Transition, which publishes the AGRIBALYSE life-cycle inventory database. A second person is asked to repeat each measurement before the finding is reported to ADEME. ADEME decides what it changes.

<!-- findings-list -->

## How to read the list

- **A row is one finding.** It shows the number, the title, what the finding concerns, its status and where it is discussed. You can search by finding number or by word, and you can show one status at a time.
- **What a finding concerns.** AGRIBALYSE processes have a name and no number. A finding says in words which process, group of processes, elementary flow or published file it is about, with the unit and the geography where they matter.
- **The status is computed from the record.** A record holds dated evidence: who reported the finding, who repeated the measurement, when it was reported to ADEME, what ADEME answered, and which AGRIBALYSE release covers the point. Nobody sets a status by hand. A step that the record does not hold is shown as "not recorded", never as done.

## What a status means

A status says how far a finding has come on its way to ADEME. Each finding's page explains its status in one sentence.

<!-- generated: status-vocabulary -->

- **"Answered by ADEME" is not "Resolved".** An answer says what ADEME said. A finding is resolved once an AGRIBALYSE release or file that the record names covers the point.
- **A change in the import is not a status.** The [import](build.md) can treat a point differently for users who need that now. It is not ADEME's correction, and it does not change the status of a finding.

## About this list

- **What counts as a finding.** Something measured on files that ADEME published, in a way that a second person can repeat. A mapping, a model, a parameter scenario or a method variant is a [contribution](contributions.md), not a finding. A defect of the import belongs to the code that introduced it, and is reported as an ordinary issue.
- **What is quoted.** Process names and single values of AGRIBALYSE. Values of the ecoinvent background are never quoted: they are licensed data (see [data and terms](../community/data-and-attribution.md)).
- **Numbers.** A finding keeps its number. The number of a finding is the number of its GitHub issue.
- **Releases.** The findings here are about AGRIBALYSE 3.2. A later release is added to the list when ADEME has published it.

Found something in the data, or want to repeat a measurement? [Take part](take-part.md) explains how.
