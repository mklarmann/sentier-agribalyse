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
})();
