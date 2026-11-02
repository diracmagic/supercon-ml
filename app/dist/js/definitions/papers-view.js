'use strict';
// papers-view: shared lexical function definitions; no startup side effects.

  // The feed lists its own sources (papers.json "sources"), so journals and news sites added later need no app update.
  const feedSources = function feedSources() {
    var d = paperState.data, js = d && d.sources && Array.isArray(d.sources.journals) ? d.sources.journals : null;
    if (!js) return { short: PAPER_SOURCES, journals: ['Nature', 'Science', 'PRL', 'PRX'], news: ['ScienceDaily', 'Phys.org', 'Physics World', 'APS Physics', 'Quanta Magazine'] };
    var short = [['all', 'All'], ['arXiv', 'arXiv']], names = [];
    js.forEach(function (j) {
      if (!Array.isArray(j) || typeof j[0] !== 'string') return;
      short.push([j[0], j[0]]);
      names.push(typeof j[1] === 'string' && j[1] ? j[1] : j[0]);
    });
    var news = d.sources && Array.isArray(d.sources.news) ? d.sources.news.filter(function (x) { return typeof x === 'string'; }) : [];
    return { short: short, journals: names, news: news };
  };

  const andList = function andList(a) { return a.length > 1 ? a.slice(0, -1).join(', ') + ' and ' + a[a.length - 1] : a.join(''); };

  // Match feed identities, never headlines or a broad topic such as "AI and data". The public AI feed is
  // already classified by feed/papers.py using named methods, superconductivity relevance and device exclusions.
  const feedIdentityKeys = function feedIdentityKeys(item) {
    var keys = [], doi = typeof item.doi === 'string' ? item.doi.trim().toLowerCase() : '';
    if (/^10\.\d{4,9}\//.test(doi)) keys.push('doi:' + doi);
    if (isHttps(item.url)) {
      try {
        var url = new URL(item.url); url.hash = '';
        Array.from(url.searchParams.keys()).forEach(function (key) { if (/^utm_|^(?:fbclid|gclid)$/.test(key)) url.searchParams.delete(key); });
        keys.push('url:' + url.href);
        if (/^(?:dx\.)?doi\.org$/i.test(url.hostname)) keys.push('doi:' + decodeURIComponent(url.pathname.slice(1)).toLowerCase());
        var arxiv = /^(?:www\.)?arxiv\.org$/i.test(url.hostname) && /^\/(?:abs|pdf)\/(\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?$/.exec(url.pathname);
        if (arxiv) keys.push('arxiv:' + arxiv[1]);
      } catch (_) { /* An invalid identity cannot match another item. */ }
    }
    if (item.id && item.source) keys.push('id:' + item.source + ':' + item.id);
    return keys;
  };

  const feedIsAI = function feedIsAI(item) {
    var keys = feedIdentityKeys(item);
    return aiItems().some(function (candidate) { return feedIdentityKeys(candidate).some(function (key) { return keys.indexOf(key) >= 0; }); });
  };


  const loadPapers = function loadPapers(force) {
    if (paperState.busy || (!force && paperState.data && Date.now() - paperState.at < 10 * 60 * 1000)) return Promise.resolve();
    paperState.busy = true;
    if (paperState.built) renderFeed();
    if (aiState.built) renderAIList();
    return getJSON(PAPERS_URL).then(function (d) {
      if (d && (Array.isArray(d.arxiv) || Array.isArray(d.journals))) { paperState.data = d; paperState.failed = false; }
      paperState.at = Date.now();
    }, function () { paperState.failed = true; }).then(function () {
      paperState.busy = false;
      if (paperState.built) renderFeed();
      if (aiState.built) renderAIList();
    });
  };


  const buildPapers = function buildPapers() {
    var el = $('#papers');
    clear(el);
    var advCard = h('section', { class: 'card' },
      h('div', { class: 'card-head' }, h('div', null, h('h2', { text: 'Recent advances' }),
        h('p', { text: 'Selected results from 2023 to 2026 in experiment and theory, each with its paper.' }))),
      h('div', { class: 'fam-filter', role: 'group', 'aria-label': 'Filter by kind', id: 'adv-filter' }),
      h('ol', { class: 'adv-list', id: 'adv-list' }),
      h('div', { class: 'feed-more', id: 'adv-more' }));
    var newsCard = h('section', { class: 'card' },
      h('div', { class: 'card-head' }, h('div', null, h('h2', { text: 'Superconductivity news' }),
        h('p', { id: 'news-sub', text: 'Recent stories from ScienceDaily, Phys.org, Physics World, APS Physics and Quanta Magazine.' }))),
      h('div', { class: 'fam-filter', role: 'group', 'aria-label': 'Filter news by source', id: 'news-src' }),
      h('ol', { class: 'feed-list', id: 'news-list' }),
      h('div', { class: 'feed-more', id: 'news-more' }),
      h('p', { class: 'note', text: 'Headlines and short snippets from each site’s public news feed, kept when they mention superconductivity; follow the links for the full stories.' }));
    var feedCard = h('section', { class: 'card' },
      h('div', { class: 'card-head' },
        h('div', null, h('h2', { text: 'New papers' }), h('p', { id: 'feed-sub', text: 'Superconductivity papers on arXiv and in Nature, Science, PRL and PRX.' })),
        h('button', { class: 'btn small', type: 'button', id: 'feed-refresh', onclick: function () { loadPapers(true); } }, 'Refresh')),
      h('div', { class: 'fam-filter', role: 'group', 'aria-label': 'Filter by source', id: 'feed-src' }),
      h('div', { class: 'feed-tools' },
        h('label', { class: 'feed-topic' }, h('span', { text: 'Topic' }), h('select', { id: 'feed-topic', onchange: function (e) { paperState.topic = e.target.value; paperState.shown = 20; renderFeed(); } }))),
      h('ol', { class: 'feed-list', id: 'feed-list' }),
      h('div', { class: 'feed-more', id: 'feed-more' }),
      h('p', { class: 'note', text: 'Updated automatically every three hours by a GitHub Actions workflow. arXiv abstracts are shown in full; for journal papers we show only the first sentence of the abstract the publisher shares through Crossref, and the rest is on the publisher’s page. Topic and type tags are assigned from keywords, so treat them as a rough guide.' }));
    var aiSection = h('section', { class: 'papers-section', id: 'papers-ai', 'aria-labelledby': 'papers-ai-heading' },
      h('h2', { class: 'papers-section-title', id: 'papers-ai-heading', text: 'AI for Superconductors' }),
      h('p', { class: 'papers-section-intro', text: 'Public research using AI to study superconducting materials. Automated feed labels are a guide, not verification of a discovery.' }),
      h('div', { id: 'papers-ai-feed' }),
      h('section', { class: 'card' }, h('div', { class: 'card-head' }, h('div', null, h('h3', { text: 'Selected AI research' }),
        h('p', { text: 'Selected public advances with their original references.' }))), h('ol', { class: 'adv-list', id: 'ai-adv-list' }), h('div', { class: 'feed-more', id: 'ai-adv-more' })));
    var generalSection = h('section', { class: 'papers-section', id: 'papers-superconductors', 'aria-labelledby': 'papers-superconductors-heading' },
      h('h2', { class: 'papers-section-title', id: 'papers-superconductors-heading', text: 'Superconductors' }),
      h('p', { class: 'papers-section-intro', text: 'Materials, mechanisms, measurements and applications. Items in the AI feed appear in the section above.' }), newsCard, feedCard, advCard);
    append(el, [aiSection, generalSection]);
    paperState.built = true;
    buildAI();
    renderAdvances();
    renderFeed();
  };


  const renderAdvances = function renderAdvances() {
    var bar = $('#adv-filter'), ol = $('#adv-list'), more = $('#adv-more');
    if (!bar || !ol) return;
    clear(bar); clear(ol); clear(more);
    if (paperState.kind === 'ai') paperState.kind = 'all';
    [['all', 'All'], ['experiment', 'Experiment'], ['theory', 'Theory and computation']].forEach(function (f) {
      bar.appendChild(h('button', { class: 'demo-tab', type: 'button', 'aria-pressed': paperState.kind === f[0] ? 'true' : 'false', text: f[1],
        onclick: function () { paperState.kind = f[0]; renderAdvances(); } }));
    });
    var rows = RECENT.filter(function (r) {
      return list(r.cards).indexOf('ai') < 0 && (paperState.kind === 'all' || (paperState.kind === 'experiment' ? r.k === 'experiment' : r.k === 'theory' || r.k === 'computation'));
    }).slice().sort(function (a, b) { return a.d < b.d ? 1 : a.d > b.d ? -1 : 0; });
    if (!paperState.advAll && rows.length > 8) {
      more.appendChild(h('button', { class: 'btn small', type: 'button', onclick: function () { paperState.advAll = true; renderAdvances(); } }, 'Show all ' + rows.length));
      rows = rows.slice(0, 8);
    }
    rows.forEach(function (r) {
      ol.appendChild(h('li', null,
        h('p', { class: 'adv-meta' }, h('span', { text: fmtMonth(r.d) }), h('span', { class: 'kind kind-' + r.k, text: KIND_LABEL[r.k] || r.k }), h('span', { text: advTopic(r) })),
        richText(h('h3'), r.h),
        richText(h('p', { class: 'adv-text' }), r.x),
        h('p', { class: 'adv-ref' }, recentLink(r))));
    });
    var aiList = $('#ai-adv-list'), aiMore = $('#ai-adv-more');
    if (aiList && aiMore) {
      clear(aiList); clear(aiMore);
      var aiRows = RECENT.filter(function (r) { return list(r.cards).indexOf('ai') >= 0; }).slice().sort(function (a, b) { return a.d < b.d ? 1 : a.d > b.d ? -1 : 0; });
      (paperState.aiAdvAll ? aiRows : aiRows.slice(0, 8)).forEach(function (r) {
        aiList.appendChild(h('li', { class: 'ai-selected-item' }, h('div', { class: 'news-art' }, miniCanvas(aiArticleArt({ title: r.h, summary: r.x, ai_kind: r.k === 'experiment' ? 'experiment' : '' })), h('span', { class: 'news-art-caption', text: 'Schematic' })),
          h('div', { class: 'news-body' }, h('p', { class: 'adv-meta' }, h('span', { text: fmtMonth(r.d) }), h('span', { class: 'kind kind-' + r.k, text: KIND_LABEL[r.k] || r.k })),
            richText(h('h3'), r.h), richText(h('p', { class: 'adv-text' }), r.x), h('p', { class: 'adv-ref' }, recentLink(r)))));
      });
      if (!aiRows.length) aiList.appendChild(h('li', { class: 'empty', text: 'No selected AI research is available yet.' }));
      if (!paperState.aiAdvAll && aiRows.length > 8) aiMore.appendChild(h('button', { class: 'btn small', type: 'button', onclick: function () { paperState.aiAdvAll = true; renderAdvances(); } }, 'Show all ' + aiRows.length));
      miniPrune(); miniKick();
    }
  };

  const advTopic = function advTopic(r) {
    var names = [];
    r.cards.forEach(function (k) {
      if (k === 'field') { names.push('Across the field'); return; }
      if (k === 'ai') { names.push('AI for superconductivity'); return; }
      THEORIES.concat(MATERIALS).forEach(function (x) { if (x.anim === k) names.push(x.name); });
    });
    return names.join(' · ');
  };


  const renderNews = function renderNews() {
    var bar = $('#news-src'), ol = $('#news-list'), more = $('#news-more');
    if (!ol) return;
    clear(bar); clear(ol); clear(more);
    miniPrune();
    var d = paperState.data, items = d ? list(d.news).filter(function (n) { return n && n.title && isHttps(n.url) && !feedIsAI(n); }) : [];
    var ns = feedSources().news, nsub = $('#news-sub');
    if (nsub && ns.length) nsub.textContent = 'Recent stories from ' + andList(ns) + '.';
    if (!d || !items.length) {
      ol.appendChild(h('li', { class: 'empty', text: !d ? (paperState.busy ? 'Loading the latest news…' : paperState.failed ? 'Couldn’t reach the news feed. Check the connection and press Refresh below.' : 'The news loads when you open this view.') : 'No superconductivity news in the feeds yet; the next check runs within three hours.' }));
      return;
    }
    var srcs = {};
    items.forEach(function (n) { srcs[n.source] = (srcs[n.source] || 0) + 1; });
    if (paperState.newsSrc !== 'all' && !srcs[paperState.newsSrc]) paperState.newsSrc = 'all';
    [['all', 'All ' + items.length]].concat(Object.keys(srcs).sort().map(function (k) { return [k, k + ' ' + srcs[k]]; })).forEach(function (f) {
      bar.appendChild(h('button', { class: 'demo-tab', type: 'button', 'aria-pressed': paperState.newsSrc === f[0] ? 'true' : 'false', text: f[1],
        onclick: function () { paperState.newsSrc = f[0]; paperState.newsShown = 10; renderNews(); } }));
    });
    var rows = items.filter(function (n) { return paperState.newsSrc === 'all' || n.source === paperState.newsSrc; });
    rows.slice(0, paperState.newsShown).forEach(function (n) {
      var meta = h('p', { class: 'paper-meta' }, h('span', { class: 'src src-news', text: n.source }), h('span', { text: fmtDayISO(n.date) }));
      list(n.topics).forEach(function (t) { meta.appendChild(h('span', { class: 'topic', text: t })); });
      ol.appendChild(h('li', { class: 'news-item' },
        h('div', { class: 'news-art' }, miniCanvas(newsArt(n)), h('span', { class: 'news-art-caption', text: 'Schematic' })),
        h('div', { class: 'news-body' }, meta, h('h3', null, h('a', { href: n.url, text: n.title })), n.summary ? h('p', { class: 'paper-intro', text: n.summary }) : null)));
    });
    miniKick();
    if (rows.length > paperState.newsShown) {
      more.appendChild(h('button', { class: 'btn small', type: 'button', onclick: function () { paperState.newsShown += 10; renderNews(); } }, 'Show more (' + (rows.length - paperState.newsShown) + ' left)'));
    }
  };


  const feedItems = function feedItems() {
    var d = paperState.data;
    if (!d) return [];
    return list(d.arxiv).concat(list(d.journals)).filter(function (p) { return p && p.title; })
      .sort(function (a, b) { return a.date < b.date ? 1 : a.date > b.date ? -1 : 0; });
  };

  const renderFeed = function renderFeed() {
    renderNews();
    var srcBar = $('#feed-src'), ol = $('#feed-list'), more = $('#feed-more'), sel = $('#feed-topic'), sub = $('#feed-sub');
    if (!ol) return;
    clear(srcBar); clear(ol); clear(more); clear(sel);
    var all = feedItems().filter(function (p) { return !feedIsAI(p); }), counts = { all: all.length };
    all.forEach(function (p) { counts[p.source] = (counts[p.source] || 0) + 1; });
    var fs = feedSources();
    if (paperState.src !== 'all' && !counts[paperState.src]) paperState.src = 'all';
    fs.short.filter(function (s) { return s[0] === 'all' || s[0] === 'arXiv' || counts[s[0]]; }).forEach(function (s) {
      srcBar.appendChild(h('button', { class: 'demo-tab', type: 'button', 'aria-pressed': paperState.src === s[0] ? 'true' : 'false',
        text: s[1] + (counts[s[0]] ? ' ' + counts[s[0]] : ''), onclick: function () { paperState.src = s[0]; paperState.shown = 20; renderFeed(); } }));
    });
    var topics = {};
    all.forEach(function (p) { list(p.topics).forEach(function (t) { topics[t] = (topics[t] || 0) + 1; }); });
    sel.appendChild(h('option', { value: 'all', text: 'All topics' }));
    Object.keys(topics).sort().forEach(function (t) { sel.appendChild(h('option', { value: t, text: t + ' (' + topics[t] + ')' })); });
    sel.value = topics[paperState.topic] ? paperState.topic : 'all';
    if (sel.value === 'all') paperState.topic = 'all';
    var d = paperState.data;
    var where = 'Superconductivity papers on arXiv and in ' + andList(fs.journals.length ? fs.journals : ['Nature', 'Science', 'PRL', 'PRX']);
    sub.textContent = d && d.updated ? where + ' · updated ' + fmtStamp(parseDate(d.updated)) : where + '.';
    if (!d) {
      ol.appendChild(h('li', { class: 'empty' }, paperState.busy ? 'Loading the latest papers…' : paperState.failed ? 'Couldn’t reach the paper feed. Check the connection and press Refresh.' : 'The paper feed loads when you open this view.'));
      return;
    }
    var rows = all.filter(function (p) {
      return (paperState.src === 'all' || p.source === paperState.src) && (paperState.topic === 'all' || list(p.topics).indexOf(paperState.topic) >= 0);
    });
    if (!rows.length) ol.appendChild(h('li', { class: 'empty', text: 'No papers match these filters yet.' }));
    rows.slice(0, paperState.shown).forEach(function (p) { ol.appendChild(paperItem(p)); });
    if (rows.length > paperState.shown) {
      more.appendChild(h('button', { class: 'btn small', type: 'button', onclick: function () { paperState.shown += 20; renderFeed(); } },
        'Show more (' + (rows.length - paperState.shown) + ' left)'));
    }
  };

  const firstSentence = function firstSentence(s) {
    var m = /^(.{40,320}?[.!?])\s+[A-Z(]/.exec(s || '');
    return m ? m[1] : (s || '').length > 300 ? s.slice(0, 297).replace(/\s+\S*$/, '') + '…' : s;
  };

  const paperItem = function paperItem(p) {
    var isArxiv = p.source === 'arXiv';
    var meta = h('p', { class: 'paper-meta' },
      h('span', { class: 'src src-' + (isArxiv ? 'arxiv' : 'journal'), text: isArxiv ? 'arXiv' + (p.cross_list ? ' (cross-list)' : '') : p.journal || p.source }),
      h('span', { text: fmtDayISO(p.date) }),
      p.kind ? h('span', { class: 'kind kind-' + p.kind, text: KIND_LABEL[p.kind] || p.kind }) : null);
    list(p.topics).forEach(function (t) { meta.appendChild(h('span', { class: 'topic', text: t })); });
    var intro = firstSentence(p.abstract);
    var body = [meta,
      h('h3', null, isHttps(p.url) ? h('a', { href: p.url, text: p.title }) : p.title),
      h('p', { class: 'paper-authors', text: list(p.authors).join(', ') })];
    if (intro) {
      body.push(h('p', { class: 'paper-intro', text: intro }));
      if (isArxiv && p.abstract && p.abstract.length > intro.length + 20) body.push(h('details', { class: 'paper-abs' }, h('summary', { text: 'Full abstract' }), h('p', { text: p.abstract })));
      else if (!isArxiv && isHttps(p.url)) body.push(h('p', { class: 'paper-more' }, h('a', { href: p.url, text: 'Full abstract on the publisher’s page' })));
    } else {
      body.push(h('p', { class: 'paper-intro muted', text: 'Published in ' + (p.journal || p.source) + '. The abstract is on the publisher’s page.' }));
    }
    if (isArxiv && p.journal_ref) body.push(h('p', { class: 'paper-authors', text: 'Published as ' + p.journal_ref }));
    return h('li', null, body);
  };

  const fmtDayISO = function fmtDayISO(s) {
    var p = String(s || '').split('-');
    return p.length >= 3 ? (+p[2]) + ' ' + MONTHS[(+p[1] || 1) - 1] + ' ' + p[0] : s || '';
  };
