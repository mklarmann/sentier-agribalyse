# AGRIBALYSE catalogue<span id="browse-agribalyse-32"></span>

Search the foods in AGRIBALYSE 3.2 by French or English name, AGRIBALYSE code or CIQUAL code. Choose **Elementary flows** or **Parameters** to explore the foreground inventory. You can bookmark or share a search using the address in your browser.

<div id="catalogue">
<form id="catalogue-controls" hidden>
<label class="field" for="catalogue-kind">Browse by
<select id="catalogue-kind" name="kind"><option value="foods">Foods</option><option value="flows">Elementary flows</option><option value="parameters">Parameters</option></select></label>
<label class="field grow" for="catalogue-search">Search
<input type="search" id="catalogue-search" name="q" autocomplete="off"></label>
</form>
<p id="catalogue-status" role="status"></p>
<ul id="catalogue-results" aria-label="Catalogue results"></ul>
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
</style>

<script defer src="assets/catalogue.js"></script>

## What the catalogue covers

Foods come from ADEME’s public table of ready-to-eat foods. Some entries share a CIQUAL code. The AGRIBALYSE code distinguishes their preparation or product variant. [ADEME’s 3.2 food table](https://data.ademe.fr/datasets/agribalyse-31-synthese) · [Open Licence](https://www.etalab.gouv.fr/licence-ouverte-open-licence).

The flow list shows names, compartments and units used in AGRIBALYSE’s own foreground processes. A flow can occur in several compartments. Parameters are listed by name and by whether they are inputs or calculated. Full exchanges, parameter values and formulas can be inspected in the [local build](build.md). [AGRIBALYSE source and terms](../IMPORT.md#licence).

If you find an unexpected value, look for the release in [Sources](sources.md) and check the [case register](cases.md) for an existing observation. Include the code or name and the release when you [report a finding](take-part.md#identify-a-finding).
