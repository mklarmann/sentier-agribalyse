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

  function appendPage() {
    const next = matches.slice(shown, shown + pageSize);
    results.append(...next.map(item));
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
    matches = catalogue[kind.value].filter(row => {
      const text = fold(row.join(" "));
      return tokens.every(token => text.includes(token));
    });
    results.replaceChildren();
    shown = 0;
    appendPage();
  }

  function update() {
    const url = new URL(location.href);
    url.searchParams.set("kind", kind.value);
    if (search.value) url.searchParams.set("q", search.value);
    else url.searchParams.delete("q");
    history.replaceState(null, "", url);
    selectResults();
  }

  async function load() {
    status.textContent = "Loading catalogue…";
    try {
      const response = await fetch(dataURL);
      if (!response.ok) throw new Error("Catalogue unavailable");
      catalogue = await response.json();
      const query = new URLSearchParams(location.search);
      kind.value = Object.hasOwn(settings, query.get("kind")) ? query.get("kind") : "foods";
      search.value = query.get("q") || "";
      selectResults();
      controls.hidden = false;
      document.querySelector("#catalogue-fallback").hidden = true;
      kind.addEventListener("change", () => { search.value = ""; update(); });
      search.addEventListener("input", update);
      controls.addEventListener("submit", event => { event.preventDefault(); update(); });
      more.addEventListener("click", () => {
        const firstNew = results.children.length;
        appendPage();
        const row = results.children[firstNew];
        if (row) { row.tabIndex = -1; row.focus(); }
      });
    } catch {
      status.textContent = "The catalogue could not be loaded. Reload this page or open ADEME’s food table below.";
    }
  }

  load();
})();
