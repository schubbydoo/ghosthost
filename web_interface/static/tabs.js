// Tab navigation: the active tab lives in the URL hash so a reload (or a link)
// lands on the same tab.
(function () {
  const tabs = Array.from(document.querySelectorAll('nav.tabs a[data-tab]'));
  const panes = Array.from(document.querySelectorAll('.tab-pane'));
  function show(name) {
    if (!panes.some(p => p.dataset.tab === name)) name = (typeof IS_AP_MODE !== 'undefined' && IS_AP_MODE) ? 'system' : 'dashboard';
    panes.forEach(p => p.classList.toggle('active', p.dataset.tab === name));
    tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === name));
    window.scrollTo(0, 0);
  }
  tabs.forEach(t => t.addEventListener('click', e => {
    e.preventDefault();
    show(t.dataset.tab);
    try { history.replaceState(null, '', '#' + t.dataset.tab); } catch (err) {}
  }));
  show(location.hash.slice(1));
})();
