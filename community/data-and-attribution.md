# Data and attribution

This public repository contains adapter code, documentation and permitted collaboration records. The code licence does not relicense ADEME's source material or ecoinvent background data.

## Attribution of ADEME's data

ADEME publishes AGRIBALYSE under the [Licence Ouverte / Etalab Open Licence 2.0](https://www.etalab.gouv.fr/licence-ouverte-open-licence). Each page that shows ADEME's data names its source and the date of its last update:

| Where it appears | Source |
|---|---|
| ADEME's values on the comparison page and in the comparison file | ADEME, AGRIBALYSE 3.2 food spreadsheet (*AGRIBALYSE3.2 Tableur produits alimentaires*, sheet *Synthese*), last updated 21 August 2025 ([data access](https://doc.agribalyse.fr/documentation-en/agribalyse-data/data-access)) |
| ADEME's results by food in the catalogue | ADEME, [AGRIBALYSE – Synthèse](https://data.ademe.fr/datasets/agribalyse-31-synthese), version 3.2, data last updated 27 February 2025 |
| Flow and parameter names; the export in the repository and the inventory downloads | ADEME, AGRIBALYSE 3.2 SimaPro export of 8 November 2024, with the ecoinvent datasets it carried removed |

The rebuilt scores are computed here from ADEME's export and a licensed ecoinvent 3.9.1 background. They are not ADEME's results, and ADEME has not reviewed or endorsed them.

## Follow the artifact's terms

[ADEME's data-access documentation](https://doc.agribalyse.fr/documentation-en/agribalyse-data/data-access) distinguishes accessible results from detailed inventories used with ecoinvent background processes. Detailed LCA use and integration of the background in tools have their own ecoinvent licensing requirements. Consult the terms for the exact release, download and intended artifact; an accessible result table does not grant permission to redistribute the linked background.

The existing adapter keeps source snapshots, background-derived CF tables, scoring caches and Brightway packages local and excluded from version control. Keep the existing publication guard active. A candidate layer that contains licensed amounts inherits their distribution constraints.

## Evidence to keep with each candidate

Record the release, source hashes, background version, method source, applied mapping packages and parameter overrides. Explain every modification and cite its evidence. Separate importer repairs, scenarios and proposed source corrections. Preserve the original baseline identity, the candidate identity and any applicable attribution or distribution conditions with exported artifacts.

The public comparison covers the published and rebuilt impact scores for all 2,451 AGRIBALYSE reference foods. The [inventory downloads](../site/build.md#download-and-reproduce-the-inventories) contain the stripped AGRIBALYSE source, its build code and the patched foreground exchanges. Reproduction uses the reviewer’s own licensed ecoinvent 3.9.1 cut-off background. Partner discussions should be linked or summarized with the contributors' permission when they are not already public.

## Recommendations to ADEME

Use evidence from the named AGRIBALYSE release. A BAFU finding is not automatically an ADEME finding. Record reviewer agreement, objections and their disposition before preparing a recommendation; a draft is not a sent message or an endorsed dataset correction. Provider responses need a public evidence link or an authorized summary.
