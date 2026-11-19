(() => {
  const controls = document.querySelector("#catalogue-controls");
  const kind = document.querySelector("#catalogue-kind");
  const search = document.querySelector("#catalogue-search");
  const status = document.querySelector("#catalogue-status");
  const results = document.querySelector("#catalogue-results");
  const more = document.querySelector("#catalogue-more");
  const dataURL = new URL("agribalyse-catalogue.json", document.currentScript.src);
  const settings = {
    foods: { example: "e.g. lentil, yaourt or 26232", singular: "food", plural: "foods" },
    flows: { example: "e.g. methane or river", singular: "flow entry", plural: "flow entries" },
    parameters: { example: "e.g. packaging or yield", singular: "parameter entry", plural: "parameter entries" }
  };
  const indicator = document.querySelector("#catalogue-indicator");
  const table = document.querySelector("#reference-table");
  const tableBody = table.querySelector("tbody");
  const referenceURL = new URL("ademe-reference.json", dataURL);
  settings.results = settings.foods;
  let reference;
  const pageSize = 20;
  let catalogue, matches, shown;

  function fold(text) {
    return text.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/œ/g, "oe");
  }

  function item(row) {
    const li = document.createElement("li");
    const title = document.createElement(kind.value === "foods" ? "a" : "strong");
    const detail = document.createElement("small");
    if (kind.value === "foods") {
      const [french, english, agb, ciqual, group] = row;
      title.textContent = english;
      title.href = "https://agribalyse.ademe.fr/app/aliments/" + encodeURIComponent(agb);
      const translation = document.createElement("div");
      translation.lang = "fr";
      translation.textContent = french;
      detail.textContent = "AGRIBALYSE " + agb + " · CIQUAL " + ciqual + " · " + group;
      li.append(title, translation, detail);
    } else {
      title.textContent = row[0];
      detail.textContent = kind.value === "flows"
        ? row.slice(1).filter(Boolean).join(" · ")
        : row[1] + " parameter";
      li.append(title, detail);
    }
    return li;
  }

  function scoreRow(row) {
    const [french, english, code] = row;
    const tr = document.createElement("tr");
    const header = document.createElement("th");
    header.scope = "row";
    const link = document.createElement("a");
    link.href = "https://agribalyse.ademe.fr/app/aliments/" + encodeURIComponent(code);
    link.textContent = english;
    const detail = document.createElement("small");
    detail.lang = "fr";
    detail.textContent = french + " · " + code;
    header.append(link, detail);
    const cell = tr.insertCell();
    const value = reference.scores[code][indicator.selectedIndex];
    cell.textContent = value == null ? "Unavailable" : String(value);
    tr.prepend(header);
    return tr;
  }

  function appendPage() {
    const next = matches.slice(shown, shown + pageSize);
    if (kind.value === "results") tableBody.append(...next.map(scoreRow));
    else results.append(...next.map(item));
    shown += next.length;
    more.hidden = shown >= matches.length;
    const { singular, plural } = settings[kind.value];
    status.textContent = matches.length
      ? "Showing " + shown.toLocaleString("en") + " of " + matches.length.toLocaleString("en") + " " + (matches.length === 1 ? singular : plural) + "."
      : "No matches. Try a shorter name or another code.";
  }

  function selectResults() {
    search.placeholder = settings[kind.value].example;
    const tokens = fold(search.value).trim().split(/\s+/).filter(Boolean);
    const scores = kind.value === "results";
    const missingScores = scores && !reference;
    table.hidden = !scores || missingScores;
    results.hidden = scores;
    document.querySelector("#reference-source").hidden = !scores;
    document.querySelector("#indicator-field").hidden = !scores || missingScores;
    if (missingScores) {
      more.hidden = true;
      status.textContent = "The impact results could not be loaded. Reload this page or open ADEME’s published table.";
      return;
    }
    if (scores) {
      const option = indicator.selectedOptions[0];
      table.caption.textContent = option.label + " (" + reference.indicators[indicator.selectedIndex].unit + " per kg of food)";
    }
    matches = catalogue[scores ? "foods" : kind.value].filter(row => {
      const text = fold(row.join(" "));
      return tokens.every(token => text.includes(token));
    });
    tableBody.replaceChildren();
    results.replaceChildren();
    shown = 0;
    appendPage();
  }

  function update() {
    const url = new URL(location.href);
    url.searchParams.set("kind", kind.value);
    if (kind.value === "results") url.searchParams.set("indicator", indicator.value);
    else url.searchParams.delete("indicator");
    if (search.value) url.searchParams.set("q", search.value);
    else url.searchParams.delete("q");
    history.replaceState(null, "", url);
    selectResults();
  }

  async function load() {
    status.textContent = "Loading catalogue…";
    try {
      async function json(url) {
        const response = await fetch(url);
        if (!response.ok) throw new Error("Catalogue unavailable");
        return response.json();
      }
      [catalogue, reference] = await Promise.all([json(dataURL), json(referenceURL).catch(() => null)]);
      for (const field of reference?.indicators || []) indicator.add(new Option(field.name, field.id));
      const query = new URLSearchParams(location.search);
      const initial = query.get("kind") || (location.hash === "#reference-results" ? "results" : "foods");
      kind.value = Object.hasOwn(settings, initial) ? initial : "foods";
      const requested = query.get("indicator");
      if (reference?.indicators.some(field => field.id === requested)) indicator.value = requested;
      search.value = query.get("q") || "";
      selectResults();
      controls.hidden = false;
      document.querySelector("#catalogue-fallback").hidden = true;
      let previous = kind.value;
      kind.addEventListener("change", () => {
        if (settings[previous] !== settings[kind.value]) search.value = "";
        previous = kind.value;
        update();
      });
      indicator.addEventListener("change", update);
      search.addEventListener("input", update);
      controls.addEventListener("submit", event => { event.preventDefault(); update(); });
      more.addEventListener("click", () => {
        const container = kind.value === "results" ? tableBody : results;
        const firstNew = container.children.length;
        appendPage();
        const row = container.children[firstNew];
        if (row) { row.tabIndex = -1; row.focus(); }
      });
    } catch {
      status.textContent = "The catalogue could not be loaded. Reload this page or open ADEME’s food table below.";
    }
  }

  load();
})();
