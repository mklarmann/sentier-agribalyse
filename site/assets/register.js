// Both registers keep searches and selected filters in the link a reviewer shares.
'use strict';
document.querySelectorAll('[data-register]').forEach(function (register) {
  const form = register.querySelector('form');
  const status = register.querySelector('[role=status]');
  const noun = register.dataset.register;
  const rows = Array.from(register.querySelectorAll('tbody tr'));
  const fields = Array.from(form.querySelectorAll('[name]'));
  function render() {
    const query = form.elements.q.value.trim().toLowerCase();
    let matches = 0;
    for (const row of rows) {
      const text = (row.textContent + ' ' + row.dataset.search).toLowerCase();
      const exactCase = noun === 'case' && /^f[1-9][0-9]*$/.test(query);
      const matchesText = exactCase ? row.dataset.case.toLowerCase() === query : text.includes(query);
      row.hidden = !matchesText || fields.some(field =>
        field.name !== 'q' && field.value && row.dataset[field.name] !== field.value);
      if (!row.hidden) matches++;
    }
    status.textContent = matches ? matches + ' of ' + rows.length + ' ' + noun + (rows.length === 1 ? '' : 's') :
      'No ' + noun + ' matches. Clear the filters to see all ' + rows.length + '.';
  }
  function load() {
    const params = new URL(location.href).searchParams;
    fields.forEach(field => {
      const value = params.get(field.name) || '';
      const previousStages = {'Needs a second measurement': 'Awaiting verification', 'Repeated, not yet reported': 'Verified, ready to report'};
      field.value = field.name === 'stage' ? previousStages[value] || value : value;
    });
    render();
  }
  function change() {
    const url = new URL(location.href);
    for (const field of fields) {
      if (field.value) url.searchParams.set(field.name, field.value);
      else url.searchParams.delete(field.name);
    }
    history.replaceState(null, '', url);
    render();
  }
  form.addEventListener('input', change);
  form.addEventListener('submit', event => { event.preventDefault(); change(); });
  form.addEventListener('reset', () => setTimeout(change, 0));
  window.addEventListener('popstate', load);
  form.hidden = false;
  load();
});
