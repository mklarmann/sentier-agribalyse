// The search, filters and sorting of a record list. The state lives in the address
// (?q=…&status=…&release=…&kind=…&patch=1&sort=…), so a view can be linked and reloaded.
//
// Findings: the page holds the most recently changed rows as HTML; the compact index named by
// data-index is loaded on first use of the search, a filter, a sort or "show more", and rows
// are drawn from it. Contributions: every row is on the page and is shown or hidden in place.
// Without this script the rows on the page and the status links still work.
(function () {
  var list = document.getElementById("list"), controls = document.getElementById("controls");
  var q = document.getElementById("q"), count = document.getElementById("count");
  if (!list || !controls || !q || !count) return;
  var noun = list.dataset.noun || "record", page = +list.dataset.page || 50, base = list.dataset.base || "";
  // What a dataset code looks like on this site (data-code); a site whose datasets have none sets none.
  var CODE = list.dataset.code ? new RegExp(list.dataset.code) : null;
  var more = document.getElementById("more"), none = document.getElementById("none"), clear = document.getElementById("clear");
  var dataset = document.getElementById("dataset"), extra = document.getElementById("more-filters");
  var chips = [].slice.call(document.querySelectorAll("[data-filter]"));
  var selects = {};
  ["status", "release", "kind", "patch", "sort"].forEach(function (name) {
    var el = document.getElementById(name);
    if (el) selects[name] = el;
  });
  var total = +list.dataset.total || list.children.length;
  var index = null, loading = null, hits = [], limit = page, timer, note = "";
  var domRows = list.dataset.index ? null : [].slice.call(list.children);
  var domText = domRows && domRows.map(function (row) { return fold(row.textContent); });
  var MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(" ");
  var SEGMENT = { d: "on", n: "now", h: "help", g: "gap" };
  // Addresses of the earlier site: findings.html#stage-<key>.
  var OLD = { "needs-triage": "filed", open: "filed,confirmed", "upstream-reported": "sent,answered",
    "upstream-fixed": "fixed", informational: "not-a-defect", "handled-in-layer": "" };

  // "CO₂" is found by "co2", "é" by "e".
  function fold(s) { return String(s).normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase(); }
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return "&#" + c.charCodeAt(0) + ";"; }); }
  function fmt(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ","); }
  function plural(n) { return fmt(n) + " " + noun + (n === 1 ? "" : "s"); }
  function day(iso) {
    var p = iso.split("-");
    return '<time datetime="' + esc(iso) + '">' + (+p[2]) + " " + MONTHS[p[1] - 1] + " " + p[0] + "</time>";
  }
  function known(name, value) {
    return !!selects[name] && [].some.call(selects[name].options, function (o) { return o.value === value; });
  }

  // ---------------------------------------------------------------- state
  var state = { q: "", status: [], release: "", kind: "", patch: "", sort: "changed" };
  function isDefault() {
    return !state.q && !state.status.length && !state.release && !state.kind && !state.patch && state.sort === "changed";
  }
  function fromUrl() {
    var params = new URLSearchParams(location.search), hash = location.hash.slice(1);
    state.q = params.get("q") || "";
    state.status = (params.get("status") || "").split(",").filter(Boolean);
    ["release", "kind", "patch"].forEach(function (name) {
      var value = params.get(name) || "";
      state[name] = known(name, value) ? value : "";
    });
    state.sort = known("sort", params.get("sort") || "") ? params.get("sort") : "changed";
    var old = hash.match(/^stage-(.+)$/);
    if (old) {
      state.status = (OLD.hasOwnProperty(old[1]) ? OLD[old[1]] : old[1]).split(",").filter(Boolean);
      if (old[1] === "handled-in-layer" && selects.patch) state.patch = "1";
    } else if (/^[FC]\d+$/.test(hash)) {
      state.q = hash; // an old link to a row of the list
    }
    var asked = state.status.length;
    state.status = state.status.filter(function (key) { return known("status", key); });
    if (asked) note = state.status.length ? "" : " No such status; showing all.";
    if (old || /^[FC]\d+$/.test(hash)) toUrl();
  }
  function toUrl() {
    var params = new URLSearchParams();
    if (state.q.trim()) params.set("q", state.q.trim());
    if (state.status.length) params.set("status", state.status.join(","));
    ["release", "kind", "patch"].forEach(function (name) { if (state[name]) params.set(name, state[name]); });
    if (state.sort !== "changed") params.set("sort", state.sort);
    var query = params.toString();
    // replaceState, never pushState: the view can be linked and reloaded, and Back leaves the list.
    history.replaceState(null, "", location.pathname + (query ? "?" + query : ""));
  }
  function toControls() {
    if (q.value.trim() !== state.q.trim()) q.value = state.q;
    if (selects.status) selects.status.value = state.status.length === 1 ? state.status[0] : "";
    ["release", "kind", "patch", "sort"].forEach(function (name) { if (selects[name]) selects[name].value = state[name]; });
    chips.forEach(function (chip) {
      if (state.status.indexOf(chip.dataset.filter) >= 0) chip.setAttribute("aria-current", "true");
      else chip.removeAttribute("aria-current");
    });
    // A filter that is set is never hidden behind "More filters".
    if (state.release || state.kind || state.patch || state.sort !== "changed") openExtra(true);
  }
  function openExtra(open) {
    if (!extra) return;
    controls.classList.toggle("open", open);
    extra.setAttribute("aria-expanded", open ? "true" : "false");
    extra.textContent = open ? "Fewer filters" : "More filters";
  }

  // ---------------------------------------------------------------- matching
  function tokens() { return fold(state.q).split(/\s+/).filter(Boolean); }
  function matcher(words) {
    // A finding number and a dataset code match exactly; any other word anywhere in the row.
    return function (r) {
      return words.every(function (w) {
        var id = /^f(\d+)$/.exec(w);
        if (id) return r[0] === +id[1];
        if (CODE && CODE.test(w)) return r[4].indexOf(+w) >= 0;
        return r.hay.indexOf(w) >= 0;
      });
    };
  }
  function prepare(data) {
    data.rows.forEach(function (r) {
      r.hay = fold(["F" + r[0], r[1], r[2], r[3], r[4].join(" "),
        r[5].map(function (i) { return data.releases[i][1]; }).join(" "), data.statuses[r[6]][1],
        r[8] >= 0 ? data.outcomes[r[8]] : "", r[10], data.kinds[r[15]][1]].join(" "));
    });
    return data;
  }
  function select() {
    var words = tokens(), ok = matcher(words);
    var releases = index.releases.map(function (x) { return x[0]; }), kinds = index.kinds.map(function (x) { return x[0]; });
    var wanted = state.status.map(function (key) {
      return index.statuses.map(function (x) { return x[0]; }).indexOf(key);
    });
    hits = index.rows.filter(function (r) {
      return (!wanted.length || wanted.indexOf(r[6]) >= 0) &&
        (!state.release || r[5].indexOf(releases.indexOf(state.release)) >= 0) &&
        (!state.kind || r[15] === kinds.indexOf(state.kind)) &&
        (!state.patch || r[9].length > 0) && ok(r);
    });
    if (state.sort === "number") hits.sort(function (a, b) { return a[0] - b[0]; });
    else if (state.sort === "waiting") hits.sort(function (a, b) {
      return (a[14] || "9999").localeCompare(b[14] || "9999") || a[0] - b[0];
    });
    // "changed" is the order of the index itself.
  }

  // ---------------------------------------------------------------- drawing
  function row(r) {
    var id = "F" + r[0], status = index.statuses[r[6]], stage;
    var releases = r[5].map(function (i) { return index.releases[i][1]; }).join(", ");
    if (r[7] === "") {
      stage = '<div class="record-stage off"><span class="stage-label">' + esc(status[1]) + '</span><span class="stage-sub">' +
        '<span class="meter off" aria-hidden="true"></span><span class="tag">off the path</span></span></div>';
    } else {
      var cells = r[7].split("").map(function (c) { return SEGMENT[c] ? '<i class="' + SEGMENT[c] + '"></i>' : "<i></i>"; }).join("");
      var tags = (r[8] >= 0 ? '<span class="tag">' + esc(index.outcomes[r[8]]) + "</span>" : "") +
        r[9].map(function (p) { return '<span class="tag">patch ' + esc(p) + "</span>"; }).join("");
      stage = '<div class="record-stage' + (status[0] === "filed" ? " help" : "") + '"><span class="stage-label">' + esc(status[1]) +
        '</span><span class="stage-sub"><span class="meter" aria-hidden="true">' + cells + "</span>" + tags + "</span></div>";
    }
    var link = /^https:\/\//.test(r[11]) ? '<a class="ext" href="' + esc(r[11]) + '">' + esc(r[10]) + "</a>" : "";
    var said = r[12] < 0 ? "" : '<span class="comments">' + (r[12] === 0 ? "no comments yet" : fmt(r[12]) + (r[12] === 1 ? " comment" : " comments")) + "</span>";
    return '<li class="record" data-stage="' + esc(status[0]) + '"><span class="record-id">' + id + "</span>" +
      '<div class="record-main"><a class="record-title" href="' + esc(base) + "findings/" + id + '.html" dir="auto">' + esc(r[1]) + "</a>" +
      '<p class="record-meta"><span class="meta-what">' + esc(r[2]) + "</span>" +
      (releases ? '\u00a0· <span class="meta-release">' + esc(releases) + "</span>" : "") + "</p></div>" + stage +
      '<div class="record-thread"><span class="thread-line">' + link + said + "</span>" +
      (r[13] ? '<span class="quiet">changed ' + day(r[13]) + "</span>" : "") + "</div></li>";
  }
  function announce(shown) {
    // One announcement per pause, not one per key.
    clearTimeout(timer);
    timer = setTimeout(function () {
      count.textContent = (shown === total ? plural(total) : fmt(shown) + " of " + plural(total)) + note;
    }, 250);
    var asked = CODE && CODE.test(state.q.trim()) ? state.q.trim() : "";
    var code = asked && !state.status.length && !state.release && !state.kind && !state.patch;
    if (dataset) { // a code that a finding names has a page of its own
      dataset.hidden = !(asked && shown > 0 && index);
      if (!dataset.hidden) {
        dataset.href = base + "datasets/" + asked + ".html";
        dataset.textContent = "All about dataset " + asked;
      }
    }
    if (none) {
      none.hidden = shown > 0;
      none.firstChild.nodeValue = code
        ? "No " + noun + " names dataset " + state.q.trim() + ". Only what someone has reported is listed. "
        : "No " + noun + " matches. ";
    }
    if (more) {
      more.hidden = shown <= limit;
      more.textContent = "Show " + Math.min(page, shown - limit) + " more";
    }
  }
  function draw(append) {
    if (domRows) {
      var words = tokens(), found = 0;
      domRows.forEach(function (el, i) {
        var ok = (!state.status.length || state.status.indexOf(el.dataset.stage) >= 0) &&
          words.every(function (w) { return domText[i].indexOf(w) >= 0; });
        if (ok) found += 1;
        var hide = !ok || found > limit;
        if (el.hidden !== hide) el.hidden = hide;
      });
      announce(found);
      return;
    }
    if (!index) return;
    if (append) list.insertAdjacentHTML("beforeend", hits.slice(limit - page, limit).map(row).join(""));
    else { select(); list.innerHTML = hits.slice(0, limit).map(row).join(""); }
    announce(hits.length);
  }
  function load() {
    if (index || domRows) return Promise.resolve();
    if (!loading) {
      list.setAttribute("aria-busy", "true");
      loading = fetch(list.dataset.index).then(function (response) {
        if (!response.ok) throw new Error(response.status);
        return response.json();
      }).then(function (data) {
        index = prepare(data);
        total = index.rows.length;
        list.removeAttribute("aria-busy");
      }).catch(function () {
        loading = null;
        list.removeAttribute("aria-busy");
        count.textContent = "The list could not be loaded. The rows below are the most recently changed.";
        throw new Error("index");
      });
    }
    return loading;
  }
  function run() {
    limit = page;
    toControls();
    // The rows of the page are already the default view: nothing is loaded until it is needed.
    if (!domRows && !index && isDefault()) { announce(total); return; }
    load().then(function () { draw(false); }, function () {});
  }
  function change() { toUrl(); run(); }

  // ---------------------------------------------------------------- events
  q.addEventListener("input", function () { state.q = q.value; change(); });
  controls.addEventListener("submit", function (event) { event.preventDefault(); });
  Object.keys(selects).forEach(function (name) {
    selects[name].addEventListener("change", function () {
      if (name === "status") state.status = selects.status.value ? [selects.status.value] : [];
      else state[name] = selects[name].value;
      note = "";
      change();
    });
  });
  chips.forEach(function (chip) {
    chip.addEventListener("click", function (event) {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return; // a new tab still works
      event.preventDefault();
      var key = chip.dataset.filter;
      state.status = state.status.length === 1 && state.status[0] === key ? [] : [key];
      note = "";
      change();
    });
  });
  if (extra) extra.addEventListener("click", function () { openExtra(!controls.classList.contains("open")); });
  if (more) more.addEventListener("click", function () {
    limit += page;
    if (domRows) draw(); else load().then(function () { if (!hits.length) select(); draw(true); }, function () {});
  });
  if (clear) clear.addEventListener("click", function () {
    state = { q: "", status: [], release: "", kind: "", patch: "", sort: "changed" };
    note = "";
    q.value = "";
    change();
    q.focus();
  });
  // Back and Reload can restore a page with other field values than its address: read it again.
  window.addEventListener("pageshow", function () { fromUrl(); run(); });
  window.addEventListener("hashchange", function () { fromUrl(); run(); });

  document.documentElement.classList.add("js");
  controls.hidden = false;
  fromUrl();
  run();
})();
