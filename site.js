// Progressive enhancement only: zoom, folds and the section index all work without this file.
(function () {
  // ---- Zoom: arrow keys cycle within a group, Esc closes ----
  function go(a) { location.replace(a.getAttribute('href')); }
  document.addEventListener('keydown', function (e) {
    if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
    var sel = { ArrowLeft: '.zp', ArrowRight: '.zn', Escape: '.zx, .lb > .x' }[e.key];
    var id = location.hash.slice(1);
    if (!sel || !id) return;
    var open = document.getElementById(id);
    var a = open && open.querySelector(sel);
    if (!a) return;
    e.preventDefault();
    go(a);
  });

  // ---- Folds: open a collapsed section when something links to it ----
  function reveal(id) {
    var el = id && document.getElementById(id);
    if (!el) return null;
    if (el.tagName === 'SECTION') {
      var f = el.querySelector('details.fold');
      if (f) f.open = true;
    }
    for (var d = el.closest('details'); d; d = d.parentElement && d.parentElement.closest('details')) d.open = true;
    return el;
  }

  // ---- Section index (sidebar on desktop, context bar on mobile) ----
  var toc = document.querySelector('.toc details');
  var label = toc && toc.querySelector('.tc');
  var links = toc ? Array.prototype.slice.call(toc.querySelectorAll('a[href^="#"]')) : [];
  var sections = links.map(function (a) { return document.getElementById(a.getAttribute('href').slice(1)); });
  var wide = window.matchMedia('(min-width:1100px)');
  function fitToc() { if (toc) toc.open = wide.matches; }
  if (wide.addEventListener) wide.addEventListener('change', fitToc);
  fitToc();

  var ticking = false;
  function spy() {
    ticking = false;
    var cur = -1;
    for (var i = 0; i < sections.length; i++) {
      if (sections[i] && sections[i].getBoundingClientRect().top <= 140) cur = i;
    }
    links.forEach(function (a, i) {
      if (i === cur) a.setAttribute('aria-current', 'location');
      else a.removeAttribute('aria-current');
    });
    if (label) label.textContent = cur < 0 ? '' : links[cur].textContent;
  }
  window.addEventListener('scroll', function () {
    if (!ticking) { ticking = true; requestAnimationFrame(spy); }
  }, { passive: true });
  window.addEventListener('resize', spy);
  spy();

  // ---- Clicks: zoom arrows, in-page links, closing the mobile index ----
  document.addEventListener('click', function (e) {
    var t = e.target;
    var arrow = t.closest && t.closest('.zp, .zn');
    if (arrow) { e.preventDefault(); go(arrow); return; }
    var a = t.closest && t.closest('a[href^="#"]');
    if (a) reveal(a.getAttribute('href').slice(1));
    if (toc && !wide.matches && toc.open && (a || !toc.contains(t))) toc.open = false;
  });

  window.addEventListener('hashchange', function () { reveal(location.hash.slice(1)); });
  var start = reveal(location.hash.slice(1));
  if (start) start.scrollIntoView();
})();
