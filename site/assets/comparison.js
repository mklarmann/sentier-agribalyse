// Keep the selection, its evidence and the dataset table on the same case.
'use strict';
(function () {
  const select = document.getElementById('review-case');
  if (!select) return;
  const opening = select.closest('.comparison-opening');
  const results = new Map(Array.from(opening.querySelectorAll('[data-result-case]'),
    template => [template.dataset.resultCase, template]));
  const result = opening.querySelector('[data-review-result]');

  function display() {
    const requested = new URL(location.href).searchParams.get('case');
    select.value = results.has(requested) ? requested : '';
    result.replaceChildren(results.get(select.value).content.cloneNode(true));
    select.dispatchEvent(new Event('comparison-case'));
  }
  select.addEventListener('change', function () {
    const url = new URL(location.href);
    if (select.value) url.searchParams.set('case', select.value);
    else url.searchParams.delete('case');
    history.pushState(null, '', url);
    display();
  });
  window.addEventListener('popstate', display);
  display();
  opening.querySelector('[data-review-filter]').hidden = false;

  // A widget route is a bookmark, not a native element ID. Let history restores
  // and ordinary section links keep the browser's scroll position.
  const initialHash = location.hash;
  const route = new URLSearchParams(initialHash.slice(1));
  const navigation = performance.getEntriesByType('navigation')[0];
  if ((route.has('sd.step') || route.has('sd.steps')) && !route.has('sd.item')
      && (!navigation || navigation.type !== 'back_forward')) {
    window.addEventListener('load', function () {
      requestAnimationFrame(function () {
        const selected = document.querySelector('.sentier-diagnostics [data-sd="step-said"]');
        if (selected && selected.textContent && location.hash === initialHash) {
          selected.scrollIntoView({ block: 'start' });
        }
      });
    }, { once: true });
  }
})();
