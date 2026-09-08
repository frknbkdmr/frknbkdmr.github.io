/* Small progressive enhancements; all source content and anchors stay in the HTML. */
(() => {
  'use strict';
  const main = document.querySelector('main.content');
  if (!main || document.body.classList.contains('home')) return;
  const tr = document.documentElement.lang.startsWith('tr');
  const terms = [...main.querySelectorAll('.term')];
  const headings = [...main.querySelectorAll('h2')];
  const anchorFor = heading => heading.id || heading.dataset.anchorId || heading.closest('section[id]')?.id;
  const insertion = main.querySelector('.lede') || main.querySelector('#title-block-header');
  let lastControl = insertion;

  // Reuse the verified translation pairing from the site's existing post-render step.
  const alternate = document.querySelector(`link[rel="alternate"][hreflang="${tr ? 'en' : 'tr'}"]`);
  if (alternate) {
    const link = document.createElement('a');
    link.className = 'translation-link no-external';
    const target = new URL(alternate.href);
    link.href = target.pathname + target.hash;
    link.hreflang = tr ? 'en' : 'tr';
    link.lang = tr ? 'en' : 'tr';
    link.textContent = tr ? 'Read in English ↗' : 'Türkçe oku ↗';
    main.querySelector('#title-block-header')?.append(link);
  }

  if (headings.length >= 3 && insertion) {
    const details = document.createElement('details');
    details.className = 'reading-nav';
    const summary = document.createElement('summary');
    summary.textContent = tr ? (terms.length ? 'Sözlükteki bölümler' : 'Bu yazıda') : 'On this page';
    const nav = document.createElement('nav');
    nav.setAttribute('aria-label', tr ? 'Sayfa içindekiler' : 'Page contents');
    const list = document.createElement('ol');
    for (const heading of headings) {
      const id = anchorFor(heading);
      if (!id) continue;
      const li = document.createElement('li');
      const a = document.createElement('a');
      a.className = 'no-external';
      a.href = '#' + encodeURIComponent(id);
      a.textContent = heading.textContent;
      li.append(a); list.append(li);
    }
    nav.append(list); details.append(summary, nav);
    insertion.after(details); lastControl = details;
  }

  if (!terms.length || !lastControl) return;
  const box = document.createElement('div');
  box.className = 'glossary-search';
  box.setAttribute('role', 'search');
  const label = document.createElement('label');
  label.htmlFor = 'term-search';
  label.textContent = tr ? 'Terim bul' : 'Find a term';
  const row = document.createElement('div'); row.className = 'search-row';
  const input = document.createElement('input');
  input.id = 'term-search'; input.type = 'search'; input.autocomplete = 'off';
  input.placeholder = tr ? 'Türkçe veya İngilizce…' : 'Turkish or English…';
  input.setAttribute('aria-describedby', 'term-search-status');
  const clear = document.createElement('button'); clear.type = 'button';
  clear.textContent = tr ? 'Temizle' : 'Clear';
  const status = document.createElement('p');
  status.id = 'term-search-status'; status.className = 'search-status';
  status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
  const results = document.createElement('ul');
  results.className = 'search-results';
  results.setAttribute('aria-label', tr ? 'Arama sonuçları' : 'Search results');
  results.hidden = true;
  row.append(input, clear); box.append(label, row, status, results); lastControl.after(box);
  const normalize = value => value.toLocaleLowerCase('tr').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/ı/g, 'i');
  const records = terms.map(term => ({term, text: normalize(term.textContent)}));
  const groups = [...new Set(terms.map(term => term.closest('section.level2')).filter(Boolean))];
  const filter = () => {
    const query = normalize(input.value.trim());
    const words = query.split(/\s+/).filter(Boolean);
    let count = 0;
    results.replaceChildren();
    results.hidden = !query;
    for (const {term, text} of records) {
      term.hidden = !words.every(word => text.includes(word));
      if (!term.hidden) {
        count++;
        if (query) {
          const item = document.createElement('li');
          const link = document.createElement('a');
          link.href = '#' + encodeURIComponent(term.id);
          link.className = 'no-external';
          link.textContent = term.querySelector('h3')?.textContent || term.id;
          item.append(link); results.append(item);
        }
      }
    }
    for (const group of groups) group.hidden = ![...group.querySelectorAll('.term')].some(term => !term.hidden);
    status.textContent = tr
      ? (count ? `${count} / ${terms.length} terim` : 'Eşleşen terim yok. Başka bir sözcük deneyin.')
      : (count ? `${count} / ${terms.length} terms` : 'No matching terms. Try another word.');
  };
  const reset = () => { input.value = ''; filter(); };
  main.addEventListener('click', event => {
    const link = event.target.closest('a[href]');
    if (input.value && link && new URL(link.href).hash && new URL(link.href).pathname === location.pathname) reset();
  });
  input.addEventListener('input', filter);
  clear.addEventListener('click', () => { reset(); input.focus(); });
  input.addEventListener('keydown', event => { if (event.key === 'Escape') { reset(); } });
  // Following a term link must reveal its target, even during a filtered search.
  window.addEventListener('hashchange', () => {
    let id; try { id = decodeURIComponent(location.hash.slice(1)); } catch { return; }
    const target = document.getElementById(id);
    if (target?.closest('.term, section.level2')) { reset(); target.scrollIntoView(); }
  });
  filter();
})();
