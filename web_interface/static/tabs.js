// Tab navigation: the active tab lives in the URL hash so a reload (or a link)
// lands on the same tab.
(function () {
  const tabs = Array.from(document.querySelectorAll('nav.tabs a[data-tab]'));
  const panes = Array.from(document.querySelectorAll('.tab-pane'));
  function show(name) {
    if (!panes.some(p => p.dataset.tab === name)) name = (typeof IS_AP_MODE !== 'undefined' && IS_AP_MODE) ? 'system' : 'dashboard';
    panes.forEach(p => p.classList.toggle('active', p.dataset.tab === name));
    tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === name));
    document.body.dataset.tab = name;
    window.scrollTo(0, 0);
  }
  tabs.forEach(t => t.addEventListener('click', e => {
    e.preventDefault();
    show(t.dataset.tab);
    try { history.replaceState(null, '', '#' + t.dataset.tab); } catch (err) {}
  }));
  // The speaking bar sticks just below the (sticky) header, so it needs the header's height
  const hdr = document.querySelector('header.site');
  function sizeHeader() { if (hdr) document.documentElement.style.setProperty('--hdr-h', hdr.offsetHeight + 'px'); }
  sizeHeader(); window.addEventListener('resize', sizeHeader); window.addEventListener('load', sizeHeader);
  // On a phone the menu scrolls sideways: open on the active tab
  function centerActive() {
    const nav = document.querySelector('nav.tabs'), a = nav && nav.querySelector('a.active');
    if (a && nav.scrollWidth > nav.clientWidth) nav.scrollLeft = a.offsetLeft - (nav.clientWidth - a.offsetWidth) / 2;
  }
  tabs.forEach(t => t.addEventListener('click', () => { setTimeout(centerActive, 0); setTimeout(sizeHeader, 0); }));
  show(location.hash.slice(1));
  centerActive();
})();
