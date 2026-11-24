/* Progressive enhancement for req-code-kb static site (zero dependencies). */
(function () {
  var root = document.documentElement;

  /* 1. Theme toggle + Mermaid theme synchronization */
  function currentTheme() {
    return root.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
  }

  function renderMermaid(theme) {
    if (typeof window.mermaid === 'undefined') return;
    var blocks = document.querySelectorAll('pre.mermaid');
    if (!blocks.length) return;
    blocks.forEach(function (el) {
      if (!el.dataset.source) {
        el.dataset.source = el.textContent;
      } else {
        el.removeAttribute('data-processed');
        el.textContent = el.dataset.source;
      }
    });
    window.mermaid.initialize({
      startOnLoad: false,
      theme: theme === 'dark' ? 'dark' : 'neutral',
      securityLevel: 'loose',
      flowchart: { curve: 'basis', padding: 14 }
    });
    try {
      window.mermaid.run({ nodes: blocks });
    } catch (e) {
      try { window.mermaid.init(undefined, blocks); } catch (_) {}
    }
  }

  renderMermaid(currentTheme());

  var toggleBtn = document.getElementById('theme-toggle');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', function () {
      var next = currentTheme() === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      try { localStorage.setItem('reqkb-theme', next); } catch (e) {}
      renderMermaid(next);
    });
  }

  /* 2. Client-side instant search / filter for knowledge cards */
  var searchInput = document.getElementById('kb-search');
  if (searchInput) {
    var countEl = document.getElementById('kb-search-count');
    var emptyEl = document.getElementById('kb-search-empty');
    var sections = document.querySelectorAll('.source-section');
    var cards = document.querySelectorAll('.card[data-search]');
    var total = cards.length;

    function applyFilter() {
      var q = searchInput.value.trim().toLowerCase();
      var visible = 0;
      cards.forEach(function (card) {
        var hay = card.getAttribute('data-search') || '';
        var match = !q || hay.indexOf(q) !== -1;
        card.hidden = !match;
        if (match) visible++;
      });
      sections.forEach(function (sec) {
        var anyVisible = sec.querySelector('.card:not([hidden])') !== null;
        sec.hidden = !anyVisible;
      });
      if (countEl) {
        countEl.textContent = q ? ('匹配 ' + visible + ' / ' + total + ' 页') : ('共 ' + total + ' 页');
      }
      if (emptyEl) {
        emptyEl.hidden = visible > 0;
      }
    }

    searchInput.addEventListener('input', applyFilter);
    applyFilter();
  }

  /* 3. Scroll-spy for per-page table of contents */
  var tocLinks = Array.prototype.slice.call(document.querySelectorAll('.toc a[href^="#"]'));
  if (tocLinks.length && 'IntersectionObserver' in window) {
    var map = {};
    var targets = [];
    tocLinks.forEach(function (a) {
      var id = decodeURIComponent(a.getAttribute('href').slice(1));
      var heading = document.getElementById(id);
      if (heading) {
        map[id] = a;
        targets.push(heading);
      }
    });
    if (targets.length) {
      var activeId = targets[0].id;
      function setActive(id) {
        tocLinks.forEach(function (a) { a.classList.remove('is-active'); });
        if (map[id]) map[id].classList.add('is-active');
      }
      setActive(activeId);
      var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            activeId = entry.target.id;
            setActive(activeId);
          }
        });
      }, { rootMargin: '-76px 0px -70% 0px', threshold: 0 });
      targets.forEach(function (t) { observer.observe(t); });
    }
  }

  /* 4. Mermaid wide-view toggle */
  document.querySelectorAll('.mermaid-expand').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var card = btn.closest('.mermaid-card');
      if (!card) return;
      var expanded = card.classList.toggle('is-expanded');
      btn.textContent = expanded ? '收起视图' : '宽屏展开';
      btn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    });
  });

  /* 5. Copy button on code blocks */
  document.querySelectorAll('.doc-main pre:not(.mermaid)').forEach(function (pre) {
    var code = pre.querySelector('code');
    if (!code || !navigator.clipboard) return;
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'copy-btn';
    btn.textContent = '复制';
    btn.addEventListener('click', function () {
      navigator.clipboard.writeText(code.textContent).then(function () {
        btn.textContent = '已复制';
        setTimeout(function () { btn.textContent = '复制'; }, 1600);
      });
    });
    pre.appendChild(btn);
  });

  /* 6. Back-to-top button */
  var topBtn = document.getElementById('back-to-top');
  if (topBtn) {
    window.addEventListener('scroll', function () {
      topBtn.classList.toggle('is-visible', window.scrollY > 360);
    }, { passive: true });
    topBtn.addEventListener('click', function () {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }
})();
