// The page of a comparison, before and after (scripts/sitebuild/beforeafter.py): sorts and
// filters the items that moved, shows more of them, and shows the results of the one chosen.
// The page holds the comparison as data; without this script it shows the first rows as they are.
'use strict';
(function () {
  var board = document.querySelector('[data-before-after]');
  if (!board) return;
  var D;
  try { D = JSON.parse(board.querySelector('[data-ba-data]').textContent); } catch (e) { return; }
  var STEP = 100;
  var q = function (sel) { return board.querySelector(sel); };
  var state = { filter: '', cause: '', group: '', kind: '', sort: null, limit: STEP, chosen: null, list: [] };
  var KINDS = D.kinds || {}, SAID = D.said || {};
  var parts = {}; // the breakdowns of single items that were loaded, by file name
  var threshold = D.threshold || 0;
  D.causes = D.causes || [];
  D.moved.forEach(function (item, i) { item.i = i; item.causes = item.causes || []; });

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  function grouped(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }
  function number(x) {
    if (x === null || x === undefined) return 'not stated';
    if (x === 0) return '0';
    var a = Math.abs(x);
    if (a < 0.001 || a >= 100000) {
      var parts = x.toExponential(2).split('e');
      return parts[0] + ' × 10<sup>' + parseInt(parts[1], 10) + '</sup>';
    }
    var shown = parseFloat(x.toPrecision(3));
    return Math.abs(shown) < 1000 ? String(shown) : grouped(Math.round(shown));
  }
  // a ratio of a value that moved: more digits where three would read "1"
  function ratioText(r) {
    var text = number(r), digits = [4, 5, 6, 8];
    for (var n = 0; n < digits.length && text === '1'; n++) text = String(parseFloat(r.toPrecision(digits[n])));
    return text;
  }
  // whether an item moved in an indicator: as the file says, where it says (its results are
  // rounded, so working it out again could differ); else from the two results
  function moved(item, id) {
    if (item.moved) return item.moved.indexOf(id) >= 0;
    var pair = item.values[id];
    if (!pair || pair[0] === null || pair[1] === null) return false;
    var size = Math.max(Math.abs(pair[0]), Math.abs(pair[1]));
    return size > 0 && Math.abs(pair[1] - pair[0]) / size > threshold;
  }
  function ratio(b, a) {
    if (b === null || a === null || b === 0 || a === 0 || (b > 0) !== (a > 0)) return null;
    var r = a / b;
    return isFinite(r) && r !== 0 ? r : null;
  }
  // how far an item lies from no change in an indicator: -1 without a pair, 0 not moved,
  // 2 without a ratio
  function distance(item, id) {
    var pair = item.values[id];
    if (!pair || pair[0] === null || pair[1] === null) return -1;
    if (!moved(item, id)) return 0;
    var r = ratio(pair[0], pair[1]);
    return r === null ? 2 : Math.abs(Math.log10(r));
  }
  function percent(b, a) {
    if (b === null || b === 0 || a === null) return '';
    var change = (a - b) / Math.abs(b) * 100, size = Math.abs(change);
    return (change > 0 ? '+' : change < 0 ? '−' : '') + size.toFixed(size >= 10 ? 0 : size >= 1 ? 1 : 2) + ' %';
  }
  function capital(s) { return s.charAt(0).toUpperCase() + s.slice(1); }
  // the class a value has is the one the file gives it: the page works none out
  function cell(item, id) {
    var pair = item.values[id], kind = (item.classes || {})[id];
    if (!pair || pair[0] === null || pair[1] === null) return '<td class="num ba-cell is-none"></td>';
    var known = kind && KINDS[kind];
    var mark = known ? ' k-' + KINDS[kind] + '" data-class="' + esc(kind) : '';
    var said = known ? capital(kind) + ': ' + SAID[kind] : null;
    var r = ratio(pair[0], pair[1]);
    if (!moved(item, id)) {
      var same = r === null || number(r) === '1';
      return '<td class="num ba-cell is-same' + mark + '" title="' +
        esc(said || (same ? 'No change' : 'Not counted as moved: within the threshold, or near zero on both sides')) + '">' + (same ? '1' : number(r)) + '</td>';
    }
    if (r === null) {
      return '<td class="num ba-cell is-opposite' + mark + '" title="' + esc('Zero, or of the other sign, on one side: no ratio' + (said ? '. ' + said : '')) + '">–</td>';
    }
    if (pair[1] === pair[0]) {
      // counted as moved by the run, by less than the results as written show
      return '<td class="num ba-cell is-slight' + mark + '" title="' + esc('Moved by less than the digits written here show' + (said ? '. ' + said : '')) + '">≈ 1</td>';
    }
    var depth = Math.max(0.12, Math.min(1, Math.abs(Math.max(-1, Math.min(1, Math.log10(r)))) * 2.2)).toFixed(2);
    // the side is where the result went: of two results below zero the lower gives the larger quotient
    return '<td class="num ba-cell is-' + (pair[1] > pair[0] ? 'above' : 'below') + mark + '"' + (said ? ' title="' + esc(said) + '"' : '') +
      ' style="--d:' + depth + '">' + ratioText(r) + '</td>';
  }
  function has(item, kind) {
    var kinds = item.classes || {};
    return Object.keys(kinds).some(function (id) { return kinds[id] === kind; });
  }
  function name(item) {
    return esc(item.name) + (item.place ? ' <span class="quiet">' + esc(item.place) + '</span>' : '');
  }

  function rows() {
    var f = state.filter.toLowerCase();
    var list = D.moved.filter(function (item) {
      return (!f || (item.name + ' ' + (item.place || '') + ' ' + item.id).toLowerCase().indexOf(f) >= 0) &&
        (!state.cause || item.causes.indexOf(state.cause) >= 0) &&
        (!state.group || item.group === state.group) &&
        (!state.kind || has(item, state.kind));
    });
    if (state.sort) {
      var s = state.sort;
      list.sort(function (x, y) { return distance(y, s) - distance(x, s) || x.i - y.i; });
    }
    return list;
  }

  function rowHtml(item) {
    var why = item.causes.map(function (c) { return '<code>' + esc(c) + '</code>'; }).join(', ');
    return '<tr data-i="' + item.i + '" tabindex="-1"' + (state.chosen === item ? ' aria-current="true"' : '') + '>' +
      '<th scope="row" class="ba-name" title="' + esc(item.name) + '">' +
      '<button type="button" class="linklike" data-ba-open>' + name(item) + '</button>' +
      (why ? '<span class="ba-why">' + why + '</span>' : '') + '</th>' +
      D.indicators.map(function (i) { return cell(item, i.id); }).join('') + '</tr>';
  }

  function head() {
    var cells = board.querySelectorAll('.ba-grid thead th[data-indicator]');
    Array.prototype.forEach.call(cells, function (th) {
      var id = th.getAttribute('data-indicator'), abbr = th.querySelector('abbr');
      if (!th.querySelector('button')) {
        var button = document.createElement('button');
        button.type = 'button'; button.className = 'ba-sort'; button.setAttribute('data-ba-sort', id);
        button.setAttribute('aria-label', abbr.title + ': sort by the distance from 1');
        th.replaceChild(button, abbr); button.appendChild(abbr);
      }
      if (state.sort === id) th.setAttribute('aria-sort', 'descending'); else th.removeAttribute('aria-sort');
    });
  }

  function counted() {
    var all = state.list.length, shown = Math.min(all, state.limit), left = all - shown;
    var word = all === 1 ? D.items.one : D.items.many;
    q('[data-ba-count]').textContent = 'Showing ' + grouped(shown) + ' of ' + grouped(all) + ' ' + word +
      (all !== D.moved.length ? ' (' + grouped(D.moved.length) + ' listed in all)' : '') +
      (state.sort ? ', the furthest from 1 first.' : '.');
    var more = q('[data-ba-more]');
    more.hidden = left <= 0;
    more.textContent = 'Show ' + grouped(Math.min(STEP, left)) + ' more';
  }

  function render() {
    head();
    state.list = rows();
    q('.ba-grid tbody').innerHTML = state.list.length ? state.list.slice(0, state.limit).map(rowHtml).join('') :
      '<tr class="empty"><td colspan="' + (D.indicators.length + 1) + '">Nothing matches these filters.</td></tr>';
    counted();
  }

  // what one result is made of, before and after, where the item has a breakdown
  function breakdown(item, found) {
    var html = '';
    D.indicators.forEach(function (i) {
      var entry = found.indicators[i.id];
      if (!entry || !entry.parts.length) return;
      var scale = 1e-300;
      entry.parts.forEach(function (x) { scale = Math.max(scale, Math.abs(x.before || 0), Math.abs(x.after || 0)); });
      var w = function (x) { return (100 * Math.abs(x || 0) / scale).toFixed(1); };
      html += '<details class="ba-item"><summary>' + esc(i.name) + ' <span class="quiet">' + esc(entry.unit || i.unit || '') + '</span></summary>' +
        '<div class="table-wrap"><table class="ba-table ba-values"><thead><tr><th scope="col">Part</th>' +
        '<th scope="col" class="num">' + esc(D.before.label) + '</th><th scope="col" class="num">' + esc(D.after.label) + '</th>' +
        '<th scope="col" class="ba-bars-head"><span class="visually-hidden">Before and after, as bars</span></th></tr></thead><tbody>' +
        entry.parts.map(function (x) {
          return '<tr><th scope="row">' + (x.kind ? '<span class="tag">' + esc(x.kind) + '</span> ' : '') + esc(x.label) + '</th>' +
            '<td class="num">' + number(x.before) + '</td><td class="num">' + number(x.after) + '</td>' +
            '<td class="ba-bars" aria-hidden="true"><span class="ba-bar is-before" style="width:' + w(x.before) + '%"></span>' +
            '<span class="ba-bar is-after" style="width:' + w(x.after) + '%"></span></td></tr>';
        }).join('') + '</tbody></table></div>' +
        (entry.parts_not_listed ? '<p class="note">' + grouped(entry.parts_not_listed) + ' smaller parts are not listed.</p>' : '') + '</details>';
    });
    return html || '<p class="list-none">The breakdown of this ' + esc(D.items.one) + ' holds no part.</p>';
  }

  function loadParts(item) {
    var place = q('[data-ba-parts]');
    if (!place || !item.detail || !/^[A-Za-z0-9][A-Za-z0-9._-]*\.json$/.test(item.detail)) return;
    var show = function (found) { if (state.chosen === item) place.innerHTML = breakdown(item, found); };
    if (parts[item.detail]) { show(parts[item.detail]); return; }
    place.innerHTML = '<p class="list-none">Loading what its results are made of.</p>';
    fetch((D.details || '') + item.detail).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (found) {
        if (!found || !found.indicators || found.item !== item.id) throw new Error('not its breakdown');
        parts[item.detail] = found; show(found);
      })
      .catch(function () { if (state.chosen === item) place.innerHTML = '<p class="list-none">Its breakdown could not be read.</p>'; });
  }

  function detail(item) {
    var word = D.word[0];
    var kinds = item.classes || null, against = item.reference || null;
    var body = D.indicators.map(function (i) {
      var pair = item.values[i.id];
      if (!pair) return '';
      var changed = moved(item, i.id);
      var r = ratio(pair[0], pair[1]);
      var scale = Math.max(Math.abs(pair[0] || 0), Math.abs(pair[1] || 0), 1e-300);
      var w = function (x) { return (100 * Math.abs(x || 0) / scale).toFixed(1); };
      return '<tr class="' + (changed ? 'is-moved' : 'is-still') + '"><th scope="row">' + esc(i.name) + '</th>' +
        '<td class="num">' + number(pair[0]) + '</td><td class="num">' + number(pair[1]) + '</td>' +
        '<td class="num">' + (changed ? (percent(pair[0], pair[1]) || '') : 'no change') + '</td>' +
        (kinds ? '<td>' + (kinds[i.id] && KINDS[kinds[i.id]] ? '<span class="ba-kind k-' + KINDS[kinds[i.id]] + '">' + esc(kinds[i.id]) + '</span>' : '') + '</td>' : '') +
        (against ? '<td class="num">' + (against[i.id] === null || against[i.id] === undefined ? '' : number(against[i.id])) + '</td>' : '') +
        '<td class="ba-bars" aria-hidden="true"><span class="ba-bar is-before" style="width:' + w(pair[0]) + '%"></span>' +
        '<span class="ba-bar is-after' + (r === null && changed ? ' is-opposite' : '') + '" style="width:' + w(pair[1]) + '%"></span></td>' +
        '<td class="quiet">' + esc(i.unit || '') + '</td></tr>';
    }).join('');
    var titles = {};
    D.causes.forEach(function (c) { titles[c.id] = c; });
    var why = item.causes.map(function (c) {
      var known = titles[c] || {};
      return '<li>' + (known.kind ? '<span class="tag">' + esc(known.kind) + '</span> ' : '') + '<code>' + esc(c) + '</code>' +
        (known.title ? ' <span class="ba-about">' + esc(known.title) + '</span>' : '') + '</li>';
    }).join('');
    return '<div class="ba-detail-head"><div><p class="card-label">' + esc(D.groups && item.group ? D.groups[item.group] : D.items.one) + '</p>' +
      '<h3 id="ba-detail-title">' + name(item) + '</h3><p class="card-meta"><code>' + esc(item.id) + '</code></p></div>' +
      '<button class="button" type="button" data-ba-close>Close</button></div>' +
      (item.note ? '<p>' + esc(item.note) + '</p>' : '') +
      (why ? '<h4>Why it moved</h4><ul class="plain">' + why + '</ul>' : '<p class="list-none">No cause is named for this ' + esc(D.items.one) + '.</p>') +
      '<h4>Its results</h4><p class="ba-legend" aria-hidden="true"><span><span class="ba-key is-before"></span>' + esc(D.before.label) + '</span> ' +
      '<span><span class="ba-key is-after"></span>' + esc(D.after.label) + '</span></p>' +
      '<div class="table-wrap"><table class="ba-table ba-values"><thead><tr><th scope="col">' + esc(word.charAt(0).toUpperCase() + word.slice(1)) + '</th>' +
      '<th scope="col" class="num">' + esc(D.before.label) + '</th><th scope="col" class="num">' + esc(D.after.label) + '</th>' +
      '<th scope="col" class="num">Change</th>' + (kinds ? '<th scope="col">Class</th>' : '') +
      (against ? '<th scope="col" class="num">' + esc((D.reference || {}).label || 'Reference') + '</th>' : '') +
      '<th scope="col" class="ba-bars-head"><span class="visually-hidden">Before and after, as bars</span></th>' +
      '<th scope="col">Unit</th></tr></thead><tbody>' + body + '</tbody></table></div>' +
      (item.detail ? '<h4>What its results are made of</h4><div data-ba-parts></div>' : '');
  }

  function open(item) {
    state.chosen = item;
    var panel = q('[data-ba-detail]');
    panel.innerHTML = detail(item);
    panel.hidden = false;
    loadParts(item);
    Array.prototype.forEach.call(board.querySelectorAll('.ba-grid tbody tr'), function (tr) {
      if (+tr.getAttribute('data-i') === item.i) tr.setAttribute('aria-current', 'true'); else tr.removeAttribute('aria-current');
    });
    panel.focus({ preventScroll: true });
    panel.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }

  function close() {
    var panel = q('[data-ba-detail]'), item = state.chosen;
    panel.hidden = true; state.chosen = null;
    var row = item && board.querySelector('.ba-grid tbody tr[data-i="' + item.i + '"]');
    var b = row && row.querySelector('[data-ba-open]');
    if (row) row.removeAttribute('aria-current');
    // a filter may have taken the row away: the filter then takes the focus
    (b || q('[data-ba-filter]')).focus();
  }

  function fill(select, field, entries) {
    if (entries.length < 2) return;
    entries.forEach(function (entry) {
      var option = document.createElement('option');
      option.value = entry[0]; option.textContent = entry[1]; select.appendChild(option);
    });
    field.hidden = false;
  }

  // ------------------------------------------------------------------ start
  var used = {};
  D.moved.forEach(function (item) { item.causes.forEach(function (c) { used[c] = 1; }); });
  fill(q('[data-ba-cause]'), q('[data-ba-cause-field]'), Object.keys(used).sort().map(function (c) { return [c, c]; }));
  fill(q('[data-ba-group]'), q('[data-ba-group-field]'), Object.keys(D.groups || {}).map(function (g) { return [g, D.groups[g]]; }));
  var met = Object.keys(KINDS).filter(function (kind) { return D.moved.some(function (item) { return has(item, kind); }); });
  fill(q('[data-ba-kind]'), q('[data-ba-kind-field]'), met.map(function (kind) { return [kind, capital(kind)]; }));
  q('.ba-controls').hidden = false;
  var fixed = board.querySelector('.ba-static');
  if (fixed) fixed.hidden = true;
  board.classList.add('is-live');
  render();

  q('[data-ba-filter]').addEventListener('input', function (e) { state.filter = e.target.value; state.limit = STEP; render(); });
  q('[data-ba-cause]').addEventListener('change', function (e) { state.cause = e.target.value; state.limit = STEP; render(); });
  q('[data-ba-group]').addEventListener('change', function (e) { state.group = e.target.value; state.limit = STEP; render(); });
  q('[data-ba-kind]').addEventListener('change', function (e) { state.kind = e.target.value; state.limit = STEP; render(); });
  // a class of the summary above the grid shows the items that have a value of that class
  Array.prototype.forEach.call(document.querySelectorAll('[data-ba-class]'), function (card) {
    var kind = card.getAttribute('data-ba-class');
    if (met.indexOf(kind) < 0 || met.length < 2) return;
    var button = document.createElement('button');
    button.type = 'button'; button.className = 'linklike'; button.textContent = 'Show these';
    button.addEventListener('click', function () {
      state.kind = kind; state.limit = STEP; q('[data-ba-kind]').value = kind; render();
      board.scrollIntoView({ block: 'start', behavior: 'smooth' });
    });
    card.appendChild(button);
  });
  q('[data-ba-more]').addEventListener('click', function () {
    var from = state.limit;
    state.limit += STEP; render();
    // the button may be gone now: the first row it added takes the focus
    var first = board.querySelectorAll('.ba-grid tbody tr[data-i] [data-ba-open]')[from];
    if (first) first.focus();
  });
  board.addEventListener('click', function (e) {
    var sort = e.target.closest('[data-ba-sort]');
    if (sort) {
      var id = sort.getAttribute('data-ba-sort');
      state.sort = state.sort === id ? null : id; state.limit = STEP; render();
      var again = board.querySelector('[data-ba-sort="' + id.replace(/"/g, '\\"') + '"]');
      if (again) again.focus();
      return;
    }
    if (e.target.closest('[data-ba-close]')) { close(); return; }
    var row = e.target.closest('.ba-grid tbody tr[data-i]');
    if (row) open(D.moved[+row.getAttribute('data-i')]);
  });
  board.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && !q('[data-ba-detail]').hidden) close();
  });
})();
