# AGRIBALYSE catalogue<span id="browse-agribalyse-32"></span>

Search the foods in AGRIBALYSE 3.2 by French or English name, AGRIBALYSE code or CIQUAL code. Choose **ADEME impact results** for the published indicators per kilogram of food. Choose **Elementary flows** or **Parameters** to explore the foreground inventory. You can bookmark or share a search using the address in your browser.

<div id="catalogue"><span id="reference-results"></span>
<form id="catalogue-controls" hidden>
<label class="field" for="catalogue-kind">Browse by
<select id="catalogue-kind" name="kind"><option value="foods">Foods</option><option value="results">ADEME impact results</option><option value="flows">Elementary flows</option><option value="parameters">Parameters</option></select></label>
<label class="field grow" for="catalogue-search">Search
<input type="search" id="catalogue-search" name="q" autocomplete="off"></label>
<label class="field" id="indicator-field" hidden for="catalogue-indicator">Impact indicator
<select id="catalogue-indicator" name="indicator"></select></label>
</form>
<div id="reference-source" hidden>
<p>ADEME’s AGRIBALYSE 3.2 food table gives the impact of one kilogram of each food. Search by food name or code and choose an indicator. Source: ADEME, <a href="https://data.ademe.fr/datasets/agribalyse-31-synthese">AGRIBALYSE – Synthèse</a>, version 3.2, data last updated 27 February 2025, <a href="https://www.etalab.gouv.fr/licence-ouverte-open-licence">Licence Ouverte / Etalab Open Licence 2.0</a>.</p>
<p>The <a href="build.html">build record</a> compares the ecoinvent rebuild with ADEME’s release.</p>
</div>
<p id="catalogue-status" role="status"></p>
<ul id="catalogue-results" aria-label="Catalogue results"></ul>
<table id="reference-table" hidden>
<caption></caption>
<thead><tr><th scope="col">Food</th><th scope="col">ADEME result</th></tr></thead>
<tbody></tbody>
</table>
<button id="catalogue-more" class="button" type="button" hidden>Show more results</button>
<p id="catalogue-fallback">Search foods directly in <a href="https://agribalyse.ademe.fr/">ADEME’s food explorer</a>. The sources below document the foreground inventory.</p>
</div>

<style>
#catalogue-controls:not([hidden]) { display: flex; flex-wrap: wrap; gap: 1rem; }
#catalogue-controls .grow { flex: 1 1 16rem; }
#catalogue-controls input, #catalogue-controls select { width: 100%; }
#catalogue-results { list-style: none; padding: 0; }
#catalogue-results li { border-top: 1px solid var(--line); margin: 0; padding: .75rem 0; overflow-wrap: anywhere; }
#catalogue-results small { display: block; color: var(--muted); }
#catalogue [hidden] { display: none; }
#catalogue-controls .field { min-width: 0; max-width: 100%; }
#reference-table { display: table; width: 100%; table-layout: fixed; }
#reference-table thead { display: table-header-group; position: static; width: auto; height: auto; clip-path: none; }
#reference-table tbody { display: table-row-group; }
#reference-table tr { display: table-row; }
#reference-table th, #reference-table td { display: table-cell; white-space: normal; overflow-wrap: anywhere; }
#reference-table thead th:last-child { width: 30%; }
#reference-table caption { text-align: left; font-weight: bold; padding: .7rem 0; }
#reference-table th, #reference-table td { vertical-align: top; padding: .6rem .4rem; }
#reference-table small { display: block; color: var(--muted); font-weight: normal; }
#reference-table thead th:last-child, #reference-table td { text-align: right; font-variant-numeric: tabular-nums; }
</style>

<script defer src="assets/catalogue.js"></script>

## What the catalogue covers

Foods come from ADEME’s public table of ready-to-eat foods. Some entries share a CIQUAL code. The AGRIBALYSE code distinguishes their preparation or product variant. Source: ADEME, [AGRIBALYSE – Synthèse](https://data.ademe.fr/datasets/agribalyse-31-synthese), version 3.2, data last updated 27 February 2025, [Licence Ouverte / Etalab Open Licence 2.0](https://www.etalab.gouv.fr/licence-ouverte-open-licence).

The flow list shows names, compartments and units used in AGRIBALYSE’s own foreground processes. Source: ADEME, AGRIBALYSE 3.2 SimaPro export of 8 November 2024, [Licence Ouverte / Etalab Open Licence 2.0](https://www.etalab.gouv.fr/licence-ouverte-open-licence). A flow can occur in several compartments. Parameters are listed by name and by whether they are inputs or calculated. Full exchanges, parameter values and formulas can be inspected in the [local build](build.md). [AGRIBALYSE source and terms](../IMPORT.md#licence).

If you find an unexpected value, look for the release in [Sources](sources.md) and check the [case register](cases.md) for an existing observation. Include the code or name and the release when you [report a finding](take-part.md#identify-a-finding).
