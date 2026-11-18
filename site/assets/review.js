// The page of a review (scripts/sitebuild/review.py): tick causes, and the page finds the two
// builds that differ by exactly them, or says which build is missing. The rule is the one of
// scripts/runrecord/review.py (`isolating`); the page holds the index as data.
'use strict';
(function () {
  var root = document.querySelector('[data-review]');
  if (!root) return;
  var D;
  try { D = JSON.parse(root.querySelector('[data-rv-data]').textContent); } catch (e) { return; }
  var runs = {}, titles = {};
  D.runs.forEach(function (run) { runs[run.id] = run; });
  D.causes.forEach(function (cause) { titles[cause.id] = cause.title || cause.id; });
  var boxes = Array.prototype.slice.call(root.querySelectorAll('[data-rv-cause]'));
  var found = root.querySelector('[data-rv-found]');

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  function grouped(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }
  function minus(a, b) { return a.filter(function (x) { return b.indexOf(x) < 0; }); }
  function named(ids) { return ids.map(function (id) { return esc(String(titles[id] || id).replace(/\.$/, '')); }).join('; '); }

  // the pair that differs by exactly the chosen causes; else the closest, and what it also holds
  function isolating(chosen) {
    var best = null, also = [], missing = chosen.slice();
    for (var n = 0; n < D.pairs.length; n++) {
      var pair = D.pairs[n], before = runs[pair.before].contains || [], after = runs[pair.after].contains || [];
      if (minus(before, after).length) continue;
      var added = minus(after, before), extra = minus(added, chosen), lacking = minus(chosen, added);
      if (!extra.length && !lacking.length) return { pair: pair, also: [], missing: [] };
      if (lacking.length === chosen.length) continue;
      if (best === null || lacking.length < missing.length || (lacking.length === missing.length && extra.length < also.length)) {
        best = pair; also = extra; missing = lacking;
      }
    }
    return { pair: null, closest: best, also: also, missing: missing };
  }

  function counts(classes) {
    if (!classes) return '';
    return '<p class="rv-counts">' + Object.keys(D.kinds).filter(function (kind) { return classes[kind]; }).map(function (kind) {
      return '<span><span class="ba-key k-' + D.kinds[kind] + '"></span><b>' + grouped(classes[kind]) + '</b> ' + esc(kind) + '</span>';
    }).join(' ') + '</p>';
  }
  function link(pair) {
    return pair.page ? '<p><a class="button primary" href="' + esc(pair.page) + '">Open the comparison</a></p>'
      : '<p class="list-none">This pair has no page of its own.</p>';
  }
  function sides(pair) {
    return '<p>Before: <strong>' + esc(runs[pair.before].label) + '</strong>. After: <strong>' + esc(runs[pair.after].label) + '</strong>.</p>';
  }

  function render() {
    var chosen = boxes.filter(function (box) { return box.checked; }).map(function (box) { return box.value; });
    if (!chosen.length) { found.hidden = true; found.innerHTML = ''; return; }
    var result = isolating(chosen), html;
    if (result.pair) {
      html = '<p><strong>Two builds differ by exactly your choice.</strong></p>' + sides(result.pair) + counts(result.pair.classes) + link(result.pair);
    } else if (result.closest) {
      html = '<p><strong>No two builds isolate your choice.</strong></p>' +
        (result.also.length ? '<p>The closest pair also contains: ' + named(result.also) + '.</p>' : '') +
        (result.missing.length ? '<p>It does not contain: ' + named(result.missing) + '.</p>' : '') +
        sides(result.closest) + counts(result.closest.classes) + link(result.closest) +
        '<p class="note">A build of the state before plus only your choice would isolate it.</p>';
    } else {
      html = '<p><strong>No two builds here differ by your choice.</strong></p>' +
        '<p class="note">Build the state before, and the state before plus your choice, and compare the two.</p>';
    }
    found.innerHTML = html;
    found.hidden = false;
  }

  boxes.forEach(function (box) { box.disabled = false; box.addEventListener('change', render); });
})();
