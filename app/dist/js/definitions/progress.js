'use strict';
// progress: shared lexical function definitions; no startup side effects.


  /* ---------- derived values ---------- */
  const runState = function runState(r) {
    if (!r) return null;
    if (r.status !== 'completed') return r.status === 'in_progress' ? 'running' : 'queued';
    switch (r.conclusion) {
      case 'success': return 'success';
      case 'failure': case 'timed_out': case 'startup_failure': return 'failure';
      case 'action_required': return 'attention';
      default: return 'cancelled';
    }
  };

  const bestBaseline = function bestBaseline(d, target) {
    var best = null;
    list(d.baselines).forEach(function (b) {
      if (b && b.target === target && b.inputs === 'structure' && typeof b.mae === 'number' && (!best || b.mae < best.mae)) best = b;
    });
    return best;
  };

  const unreleased = function unreleased(d) {
    var out = {}, am = (d && d.ai_model) || {};
    list(am.versions).concat(am.ensemble ? [am.ensemble] : []).forEach(function (v) {
      if (v && v.version && v.status && v.status !== 'adopted') out['Storm ' + v.version + ' (AI-designed)'] = 1;
    });
    list(d && d.gnn && d.gnn.versions).forEach(function (v) {
      if (v && v.version && v.status && v.status !== 'adopted') out['Graph neural network ' + v.version + ' (AI-designed)'] = 1;
    });
    return out;
  };

  const bestOurs = function bestOurs(d, target) {
    var best = null, skip = unreleased(d);
    list(d.results).concat(list(d.history)).forEach(function (r) {
      if (r && r.target === target && typeof r.mae === 'number' && !skip[String(r.model)] && (!best || r.mae < best.mae)) best = r;
    });
    return best;
  };

  const ghMessage = function ghMessage(p) {
    if (!p) return '';
    if (p.kind === 'missing') return t('repoMissing');
    if (p.kind === 'rate') return t('rateLimited', { t: fmtTime(new Date(p.until)) });
    return t('ghError');
  };


  /* ---------- rendering ---------- */
  const setBusy = function setBusy(on) { $('#btn-refresh').classList.toggle('is-busy', on); };


  const cardHead = function cardHead(title, sub, action) {
    return h('div', { class: 'card-head' },
      h('div', null, h('h2', { text: title }), sub ? h('p', { text: sub }) : null),
      action || null);
  };

  const tile = function tile(label) {
    return h('div', { class: 'card tile' }, h('p', { class: 'tile-label', text: label }), Array.prototype.slice.call(arguments, 1));
  };

  const chip = function chip(kind, label) { return h('span', { class: 'chip' }, h('i', { class: 'd-' + kind }), label); };

  const targetNode = function targetNode(target) {
    var map = { Tc: ['T', 'c'], Tc_exp: ['T', 'c', ' (measured)'], omega_log: ['ω', 'log'], lambda: ['λ', null] };
    var m = map[target];
    if (!m) return document.createTextNode(String(target || ''));
    return h('span', null, m[0], m[1] ? h('sub', { text: m[1] }) : null, m[2] || null);
  };


  const renderChrome = function renderChrome() {
    document.title = t('appName');
    $('#app-name').textContent = t('appName');
    $('#project').textContent = state.data ? L(state.data.project) : '';

    var up = state.data ? parseDate(state.data.updated) : null;
    $('#stamp').textContent = up ? t('updated', { t: rel(up) }) : (state.loaded ? '' : t('loading'));
    $('#live-dot').className = 'live-dot' + (state.live === 'ok' ? ' is-live' : state.live ? ' is-off' : '');

    var r = $('#btn-refresh');
    if (!r.firstChild) r.innerHTML = G.refresh;
    var rl = state.checkedAt ? t('checked', { t: fmtTime(state.checkedAt) }) : t('refresh');
    r.title = rl;
    r.setAttribute('aria-label', rl);


    var tb = $('#btn-theme');
    tb.innerHTML = G[theme];
    var tl = t(theme === 'light' ? 'themeLight' : theme === 'dark' ? 'themeDark' : 'themeSystem');
    tb.title = tl;
    tb.setAttribute('aria-label', tl);

    var notice = $('#notice');
    var msg = '';
    if (state.data && state.live === 'missing') msg = t('notPublished', { t: up ? fmtStamp(up) : '—' });
    else if (state.data && state.live === 'offline') msg = t('offline', { t: up ? fmtStamp(up) : '—' });
    else if (!state.data && state.loaded) msg = t('noData');
    clear(notice);
    if (msg) { append(notice, [glyph('info', 'notice-glyph'), h('span', { text: msg })]); notice.hidden = false; }
    else notice.hidden = true;

    var foot = $('#foot');
    clear(foot);
    append(foot, [
      h('span', null, t('appName') + ' ' + APP_VERSION, h('span', { id: 'upd-foot', class: 'upd-foot' })),
      h('span', null, h('a', { href: REPO_URL, text: 'github.com/' + REPO }), ' · ' + t('footData'))
    ]);
    renderUpdateFoot();
  };


  const reducedMotion = function reducedMotion() {
    return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  };

  const currentIndex = function currentIndex(stages) {
    var pick = function (st) { for (var i = 0; i < stages.length; i++) if (stages[i].status === st) return i; return -1; };
    var i = pick('active');
    if (i < 0) i = pick('blocked');
    if (i < 0) for (var j = 0; j < stages.length; j++) if (stages[j].status !== 'done') { i = j; break; }
    return i;
  };

  const countUp = function countUp(el, from, to, ms) {
    if (reducedMotion() || from === to || !window.requestAnimationFrame) { el.textContent = to + '%'; return; }
    var t0 = null;
    function frame(now) {
      if (t0 === null) t0 = now;
      var k = Math.min(1, (now - t0) / ms);
      var e = 1 - Math.pow(1 - k, 3);
      el.textContent = Math.round(from + (to - from) * e) + '%';
      if (k < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  };

  const renderPipeline = function renderPipeline(d) {
    var el = $('#pipeline');
    clear(el);
    var stages = list(d.stages);
    var n = stages.length;
    var done = stages.filter(function (x) { return x.status === 'done'; }).length;
    var ci = currentIndex(stages);
    var cur = ci >= 0 ? stages[ci] : null;
    var pct = n ? Math.round(done / n * 100) : 0;
    var nowText = cur ? t('now', { s: L(cur.name) }) : t('allDone');
    var num = h('span', { text: (state.shownPct === null ? 0 : state.shownPct) + '%' });
    el.appendChild(h('div', { class: 'pipe-head' },
      h('div', null, h('p', { class: 'tile-label', text: t('progress') }), h('p', { class: 'hero' }, num)),
      h('div', { class: 'pipe-meta' },
        h('p', { class: 'pipe-strong', text: t('stagesDone', { d: done, n: n }) }),
        h('p', { class: 'tile-sub', text: nowText }))));
    countUp(num, state.shownPct === null ? 0 : state.shownPct, pct, 1100);
    state.shownPct = pct;

    var host = h('div', { class: 'pipe', role: 'img', 'aria-label': t('pipelineAria', { d: done, n: n, s: nowText }) });
    el.appendChild(host);
    if (pipeObserver) { pipeObserver.disconnect(); pipeObserver = null; }
    if (window.ResizeObserver) {
      var lastW = 0;
      pipeObserver = new ResizeObserver(function (entries) {
        var w = Math.floor(entries[0].contentRect.width);
        if (w && Math.abs(w - lastW) > 4) { lastW = w; drawPipeline(host, stages, ci); }
      });
      pipeObserver.observe(host);
    } else {
      setTimeout(function () { drawPipeline(host, stages, ci); }, 0);
    }
  };


  const drawPipeline = function drawPipeline(host, stages, ci) {
    clear(host);
    var n = stages.length;
    if (!n) return;
    var W = Math.max(280, Math.floor(host.getBoundingClientRect().width) || 800);
    var H = 64;
    var padX = 14;
    var y = 16;
    var spacing = n > 1 ? (W - 2 * padX) / (n - 1) : 0;
    var showAll = spacing >= 92;
    var motion = !reducedMotion();
    var intro = motion && !state.pipeIntro;
    function X(i) { return n === 1 ? W / 2 : padX + i * spacing; }

    var svg = s('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, class: 'pipe-svg', 'aria-hidden': 'true' });
    svg.appendChild(s('line', { x1: X(0), x2: X(n - 1), y1: y, y2: y, class: 'pipe-track' }));
    var end = ci >= 0 ? X(ci) : X(n - 1);
    var len = end - X(0);
    if (len > 0) {
      var fill = s('line', { x1: X(0), x2: end, y1: y, y2: y, class: 'pipe-fill' });
      if (intro) {
        fill.style.strokeDasharray = len + ' ' + len;
        fill.style.strokeDashoffset = String(len);
        requestAnimationFrame(function () {
          requestAnimationFrame(function () {
            fill.style.transition = 'stroke-dashoffset 1.2s cubic-bezier(0.2, 0.7, 0.2, 1)';
            fill.style.strokeDashoffset = '0';
          });
        });
      }
      svg.appendChild(fill);
    }
    if (motion && ci > 0 && stages[ci].status !== 'blocked') {
      var comet = s('circle', { cx: X(ci - 1), cy: y, r: 2.5, class: 'pipe-comet', opacity: 0 });
      comet.appendChild(s('animate', { attributeName: 'cx', from: X(ci - 1), to: X(ci), dur: '1.8s', begin: intro ? '1.2s' : '0s', repeatCount: 'indefinite' }));
      comet.appendChild(s('animate', { attributeName: 'opacity', values: '0;0.95;0.95;0', keyTimes: '0;0.15;0.75;1', dur: '1.8s', begin: intro ? '1.2s' : '0s', repeatCount: 'indefinite' }));
      svg.appendChild(comet);
    }
    stages.forEach(function (st, i) {
      var status = STAGE_STATUSES.indexOf(st.status) >= 0 ? st.status : 'pending';
      var g = s('g', { transform: 'translate(' + X(i).toFixed(1) + ' ' + y + ')' });
      if (status === 'active' && motion) {
        var halo = s('circle', { r: 10, class: 'pipe-halo', opacity: 0 });
        halo.appendChild(s('animate', { attributeName: 'r', values: '10;22', dur: '1.8s', repeatCount: 'indefinite' }));
        halo.appendChild(s('animate', { attributeName: 'opacity', values: '0.35;0', dur: '1.8s', repeatCount: 'indefinite' }));
        g.appendChild(halo);
      }
      var node = s('g', intro ? { class: 'pipe-pop', style: 'animation-delay:' + (i * 90) + 'ms' } : {});
      if (status === 'done') {
        node.appendChild(s('circle', { r: 11, class: 'f-good' }));
        node.appendChild(s('path', { d: 'M-4.6 0.4l3 3 6-6.4', class: 's-white', fill: 'none', 'stroke-width': 2.2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }));
      } else if (status === 'active') {
        node.appendChild(s('circle', { r: 10, class: 'f-surface s-accent', 'stroke-width': 2.5 }));
        node.appendChild(s('circle', { r: 4.5, class: 'f-accent' }));
      } else if (status === 'blocked') {
        node.appendChild(s('circle', { r: 11, class: 'f-warning' }));
        node.appendChild(s('path', { d: 'M0 -5v6', stroke: '#0b0b0b', 'stroke-width': 2.2, 'stroke-linecap': 'round' }));
        node.appendChild(s('circle', { cy: 4.6, r: 1.3, fill: '#0b0b0b' }));
      } else {
        node.appendChild(s('circle', { r: 8, class: 'f-surface s-axis', 'stroke-width': 2 }));
      }
      g.appendChild(node);
      svg.appendChild(g);
      if (showAll || i === ci) {
        var anchor = 'middle';
        var lx = X(i);
        if (n > 1 && i === 0) { anchor = 'start'; lx = X(i) - 11; }
        else if (n > 1 && i === n - 1) { anchor = 'end'; lx = X(i) + 11; }
        else if (!showAll) {
          if (lx < 70) { anchor = 'start'; lx = X(i) - 11; }
          else if (lx > W - 70) { anchor = 'end'; lx = X(i) + 11; }
        }
        svg.appendChild(s('text', { x: lx, y: y + 38, 'text-anchor': anchor, class: 'pipe-label' + (i === ci ? ' is-current' : '') }, L(st.short) || L(st.name)));
      }
    });
    host.appendChild(svg);
    if (intro) state.pipeIntro = true;
  };


  const renderKpis = function renderKpis(d) {
    var el = $('#kpis');
    clear(el);

    var run = list(state.runs)[0];
    if (run) {
      var k = runState(run);
      var when = parseDate(run.run_started_at || run.created_at);
      el.appendChild(tile(t('latestBuild'),
        h('p', { class: 'tile-status' }, glyph(RUN_GLYPH[k], ''), h('span', { text: t('run_' + k) })),
        h('p', { class: 'tile-sub' }, isHttps(run.html_url) ? h('a', { href: run.html_url, text: run.display_title || run.name || '' }) : (run.display_title || run.name || '')),
        h('p', { class: 'tile-sub muted', text: [run.name, when ? rel(when) : ''].filter(Boolean).join(' · ') })));
    } else {
      el.appendChild(tile(t('latestBuild'),
        h('p', { class: 'tile-value dim', text: '—' }),
        h('p', { class: 'tile-sub', text: state.gh ? ghMessage(state.gh) : (state.runs ? t('noRuns') : t('loading')) })));
    }

    var best = bestOurs(d, 'Tc');
    var ref = bestBaseline(d, 'Tc');
    el.appendChild(tile(t('bestTc'),
      best ? h('p', { class: 'tile-value' }, fmtVal(best.mae), h('small', { text: 'K' })) : h('p', { class: 'tile-value dim', text: '—' }),
      h('p', { class: 'tile-sub', text: best ? L(best.model) : t('noModel') }),
      ref ? h('p', { class: 'tile-sub muted', text: t('vsBaseline', { v: fmtVal(ref.mae) + ' K, ' + L(ref.model) }) }) : null));

    var tg = d.target ? parseDate(d.target.date) : null;
    if (tg) {
      var days = daysUntil(tg);
      el.appendChild(tile(t('target'),
        h('p', { class: 'tile-value', text: fmtDay(tg) }),
        h('p', { class: 'tile-sub', text: days > 1 ? t('daysLeft', { n: days }) : days === 1 ? t('dayLeft') : days === 0 ? t('dueToday') : t('overdue', { n: -days }) })));
    }
  };


  const renderStages = function renderStages(d) {
    var el = $('#stages-card');
    clear(el);
    el.appendChild(cardHead(t('stages'), t('stagesSub')));
    var ol = h('ol', { class: 'steps' });
    list(d.stages).forEach(function (st) {
      var status = STAGE_STATUSES.indexOf(st.status) >= 0 ? st.status : 'pending';
      var date = parseDate(st.date);
      var dateText = '';
      if (date) dateText = (status === 'pending' && daysUntil(date) > 0) ? t('targetOn', { d: fmtDay(date) }) : fmtDay(date);
      ol.appendChild(h('li', { class: 'step is-' + status },
        glyph(status, 'step-icon'),
        h('div', null,
          h('div', { class: 'step-head' },
            h('span', { class: 'step-name', text: L(st.name) }),
            chip(status, t('st_' + status)),
            dateText ? h('span', { class: 'step-date', text: dateText }) : null),
          st.detail ? h('p', { class: 'step-detail', text: L(st.detail) }) : null)));
    });
    el.appendChild(ol);
  };


  const renderActivity = function renderActivity(d) {
    var el = $('#activity-card');
    clear(el);
    el.appendChild(cardHead(t('activity')));
    var items = list(d.log).map(function (x) { return { at: parseDate(x && x.at), text: L(x && x.event) }; })
      .filter(function (x) { return x.text; })
      .sort(function (a, b) { return (b.at ? b.at.getTime() : 0) - (a.at ? a.at.getTime() : 0); });
    if (!items.length) { el.appendChild(h('p', { class: 'muted-p', text: '—' })); return; }
    var ul = h('ul', { class: 'feed' });
    (state.showAllLog ? items : items.slice(0, LOG_LIMIT)).forEach(function (x) {
      ul.appendChild(h('li', null,
        h('time', { datetime: x.at ? x.at.toISOString() : null, text: x.at ? fmtStamp(x.at) : '' }),
        h('p', { text: x.text })));
    });
    el.appendChild(ul);
    if (items.length > LOG_LIMIT) {
      el.appendChild(h('button', {
        class: 'link-btn', type: 'button',
        text: state.showAllLog ? t('showLess') : t('showAll', { n: items.length }),
        onclick: function () { state.showAllLog = !state.showAllLog; renderActivity(state.data); }
      }));
    }
  };


  const renderGitHub = function renderGitHub() {
    var el = $('#github-card');
    clear(el);
    el.appendChild(cardHead(t('onGithub'), null, h('a', { class: 'head-link', href: REPO_URL, text: t('openRepo') })));
    var runs = list(state.runs).slice(0, 5);
    var commits = list(state.commits).slice(0, 5);
    if (state.gh && !runs.length && !commits.length) {
      el.appendChild(h('p', { class: 'muted-p', text: ghMessage(state.gh) }));
      return;
    }
    el.appendChild(h('h3', { class: 'sub-h', text: t('runs') }));
    if (!runs.length) el.appendChild(h('p', { class: 'muted-p', text: state.runs ? t('noRuns') : t('loading') }));
    else {
      var ul = h('ul', { class: 'gh-list' });
      runs.forEach(function (r) {
        var k = runState(r);
        var when = parseDate(r.run_started_at || r.created_at);
        var meta = [t('run_' + k), r.name, r.run_number ? '#' + r.run_number : '', when ? rel(when) : ''].filter(Boolean).join(' · ');
        ul.appendChild(h('li', null, h('a', { class: 'gh-item', href: isHttps(r.html_url) ? r.html_url : null },
          glyph(RUN_GLYPH[k], 'gh-icon'),
          h('span', { class: 'gh-text' },
            h('span', { class: 'gh-title', text: r.display_title || r.name || '' }),
            h('span', { class: 'gh-meta', text: meta })))));
      });
      el.appendChild(ul);
    }
    el.appendChild(h('h3', { class: 'sub-h', text: t('commits') }));
    if (!commits.length) el.appendChild(h('p', { class: 'muted-p', text: state.commits ? t('noCommits') : t('loading') }));
    else {
      var cl = h('ul', { class: 'gh-list' });
      commits.forEach(function (c) {
        var info = c && c.commit ? c.commit : {};
        var msg = String(info.message || '').split('\n')[0];
        var when = parseDate(info.author && info.author.date);
        cl.appendChild(h('li', null, h('a', { class: 'gh-item', href: isHttps(c.html_url) ? c.html_url : null },
          glyph('commit', 'gh-icon'),
          h('span', { class: 'gh-text' },
            h('span', { class: 'gh-title', text: msg }),
            h('span', { class: 'gh-meta' }, h('span', { class: 'sha', text: String(c.sha || '').slice(0, 7) }), when ? ' · ' + rel(when) : '')))));
      });
      el.appendChild(cl);
    }
    if (state.gh) el.appendChild(h('p', { class: 'muted-p', text: ghMessage(state.gh) }));
  };

  const renderResults = function renderResults(d) {
    var el = $('#results-card');
    clear(el);
    var pts = list(d.history)
      .filter(function (x) { return x && x.target === 'Tc' && typeof x.mae === 'number' && (!x.split || x.split === 'val'); })
      .map(function (x) { return { at: parseDate(x.at), y: x.mae, model: L(x.model) }; })
      .sort(function (a, b) { return (a.at ? a.at.getTime() : 0) - (b.at ? b.at.getTime() : 0); });
    var ref = bestBaseline(d, 'Tc');
    var toggle = pts.length ? h('button', {
      class: 'btn small', type: 'button',
      text: state.view === 'chart' ? t('showTable') : t('showChart'),
      onclick: function () { state.view = state.view === 'chart' ? 'table' : 'chart'; renderResults(state.data); }
    }) : null;
    el.appendChild(cardHead(t('results'), t('resultsSub'), toggle));

    var fig = h('figure', { class: 'figure' }, h('figcaption', { class: 'fig-title', text: t('chartTitle') }));
    if (chartObserver) { chartObserver.disconnect(); chartObserver = null; }
    if (!pts.length) {
      fig.appendChild(h('div', { class: 'empty' }, glyph('chart', ''), h('p', { text: t('chartEmpty') })));
    } else if (state.view === 'table') {
      fig.appendChild(historyTable(pts));
    } else {
      var host = h('div', { class: 'chart' });
      fig.appendChild(host);
      if (window.ResizeObserver) {
        var lastW = 0;
        chartObserver = new ResizeObserver(function (entries) {
          var w = Math.floor(entries[0].contentRect.width);
          if (w && Math.abs(w - lastW) > 4) { lastW = w; drawChart(host, pts, ref); }
        });
        chartObserver.observe(host);
      } else {
        setTimeout(function () { drawChart(host, pts, ref); }, 0);
      }
    }
    el.appendChild(fig);
    el.appendChild(resultsTable(d));
    el.appendChild(h('p', { class: 'note', text: t('baselineNote') }));
  };


  const historyTable = function historyTable(pts) {
    var tb = h('tbody');
    pts.forEach(function (p, i) {
      tb.appendChild(h('tr', null,
        h('td', { class: 'num', text: '#' + (i + 1) }),
        h('td', { text: p.at ? fmtStamp(p.at) : '' }),
        h('td', { text: p.model || t('thisProject') }),
        h('td', { class: 'num', text: fmtVal(p.y) + ' K' })));
    });
    return h('div', { class: 'tbl-wrap' }, h('table', { class: 'tbl' },
      h('thead', null, h('tr', null,
        h('th', { class: 'num', text: t('colRun') }), h('th', { text: t('colDate') }),
        h('th', { text: t('colModel') }), h('th', { class: 'num', text: t('colMae') }))),
      tb));
  };


  const stormResultRows = function stormResultRows() {
    var info = stormInfo();
    if (!info) return [];
    var v = info.v, sc = v.scores;
    return [{ ours: true, r: { model: stormTitle(info) + ' (AI-designed)', target: 'Tc', mae: sc.tc_mae, unit: 'K',
      note: 'Best of ' + (v.search ? v.search.candidates : 'several') + ' AI-designed candidates; same 5-fold composition-grouped CV; better than ' + (sc.previous ? sc.previous.name + ' in ' + sc.previous.folds_better : 'the baseline in ' + sc.folds_better) + ' of ' + list(sc.folds).length + ' folds' + (v.status === 'adopted' ? '' : '; experimental') } }];
  };

  const resultsTable = function resultsTable(d) {
    var rows = stormResultRows().concat(list(d.results).map(function (r) { return { r: r, ours: true }; }))
      .concat(list(d.baselines).map(function (r) { return { r: r, ours: false }; }));
    var tb = h('tbody');
    rows.forEach(function (row) {
      var r = row.r || {};
      var unit = r.unit ? ' ' + r.unit : '';
      var note = L(r.note);
      var notes = [note];
      if (r.source) notes.push(note ? ' · ' : '', isHttps(r.link) ? h('a', { href: r.link, text: r.source }) : r.source);
      tb.appendChild(h('tr', { class: row.ours ? 'ours' : null },
        h('td', null, L(r.model), row.ours ? h('span', { class: 'tag', text: t('thisProject') }) : null),
        h('td', null, targetNode(r.target)),
        h('td', { class: 'num', text: typeof r.mae === 'number' ? fmtVal(r.mae) + unit : '—' }),
        h('td', { class: 'notes' }, notes)));
    });
    return h('div', { class: 'tbl-wrap' }, h('table', { class: 'tbl' },
      h('thead', null, h('tr', null,
        h('th', { text: t('colModel') }), h('th', { text: t('colTarget') }),
        h('th', { class: 'num', text: t('colMae') }), h('th', { text: t('colNotes') }))),
      tb));
  };


  const drawChart = function drawChart(host, pts, ref) {
    clear(host);
    var W = Math.max(280, Math.floor(host.getBoundingClientRect().width) || 600);
    var H = 228;
    var m = { t: 12, r: 12, b: 28, l: 40 };
    var pw = W - m.l - m.r;
    var ph = H - m.t - m.b;
    var vals = pts.map(function (p) { return p.y; });
    if (ref) vals.push(ref.mae);
    var top = Math.max.apply(null, vals) * 1.15 || 1;
    var step = niceStep(top, 4);
    var yMax = Math.ceil(top / step) * step;
    var n = pts.length;
    function X(i) { return m.l + (n === 1 ? pw / 2 : i * pw / (n - 1)); }
    function Y(v) { return m.t + ph - v / yMax * ph; }

    var svg = s('svg', {
      viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, class: 'plot', role: 'img', tabindex: '0',
      'aria-label': t('chartTitle') + ': ' + pts.map(function (p) { return fmtVal(p.y) + ' K'; }).join(', ')
    });
    for (var v = 0; v <= yMax + step * 1e-6; v += step) {
      var yy = Math.round(Y(v)) + 0.5;
      svg.appendChild(s('line', { x1: m.l, x2: W - m.r, y1: yy, y2: yy, class: v === 0 ? 'axis-line' : 'grid-line' }));
      svg.appendChild(s('text', { x: m.l - 8, y: yy + 4, 'text-anchor': 'end', class: 'tick' }, fmtTick(v)));
    }
    var ticks = n === 1 ? [0] : n < 6 ? pts.map(function (_, i) { return i; }) : [0, Math.floor((n - 1) / 2), n - 1];
    ticks.forEach(function (i) {
      var anchor = n === 1 ? 'middle' : i === 0 ? 'start' : i === n - 1 ? 'end' : 'middle';
      svg.appendChild(s('text', { x: X(i), y: H - 8, 'text-anchor': anchor, class: 'tick' }, pts[i].at ? fmtDay(pts[i].at) : '#' + (i + 1)));
    });
    var last = n - 1;
    if (ref) {
      var ry = Math.round(Y(ref.mae)) + 0.5;
      var near = Math.abs(Y(pts[last].y) - ry) < 22;
      svg.appendChild(s('line', { x1: m.l, x2: W - m.r, y1: ry, y2: ry, class: 'ref-line' }));
      svg.appendChild(s('text', { x: m.l + 6, y: near ? ry + 15 : ry - 6, class: 'ref-label' }, t('refLabel', { m: L(ref.model), v: fmtVal(ref.mae) + ' K' })));
    }
    if (n > 1) {
      svg.appendChild(s('path', { class: 'series-line', d: pts.map(function (p, i) { return (i ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(p.y).toFixed(1); }).join(' ') }));
    }
    pts.forEach(function (p, i) { svg.appendChild(s('circle', { cx: X(i), cy: Y(p.y), r: 4, class: 'series-dot' })); });
    svg.appendChild(s('text', {
      x: n === 1 ? X(last) : X(last) - 8, y: Y(pts[last].y) - 10,
      'text-anchor': n === 1 ? 'middle' : 'end', class: 'end-label'
    }, fmtVal(pts[last].y) + ' K'));

    var cross = s('line', { y1: m.t, y2: m.t + ph, class: 'crosshair', visibility: 'hidden' });
    var ring = s('circle', { r: 6.5, class: 'hover-dot', visibility: 'hidden' });
    var hit = s('rect', { x: m.l - 16, y: 0, width: pw + 32, height: m.t + ph + 8, fill: 'transparent' });
    svg.appendChild(cross);
    svg.appendChild(ring);
    svg.appendChild(hit);
    var tip = h('div', { class: 'tooltip', hidden: true });
    host.appendChild(svg);
    host.appendChild(tip);

    var cur = -1;
    function show(i) {
      cur = i;
      var p = pts[i];
      var x = X(i);
      var y = Y(p.y);
      cross.setAttribute('x1', x); cross.setAttribute('x2', x); cross.setAttribute('visibility', 'visible');
      ring.setAttribute('cx', x); ring.setAttribute('cy', y); ring.setAttribute('visibility', 'visible');
      clear(tip);
      append(tip, [
        h('b', { text: fmtVal(p.y) + ' K' }),
        h('span', { class: 'tip-row' }, h('i', { class: 'key' }), p.model || t('thisProject')),
        h('span', { class: 'tip-row', text: p.at ? fmtStamp(p.at) : '#' + (i + 1) })
      ]);
      tip.hidden = false;
      tip.style.left = Math.min(Math.max(x, 86), W - 86) + 'px';
      tip.style.top = y + 'px';
    }
    function hide() {
      cur = -1;
      cross.setAttribute('visibility', 'hidden');
      ring.setAttribute('visibility', 'hidden');
      tip.hidden = true;
    }
    function nearest(evt) {
      var box = svg.getBoundingClientRect();
      var px = (evt.clientX - box.left) * (W / box.width);
      var best = 0;
      var bd = Infinity;
      for (var i = 0; i < n; i++) { var dd = Math.abs(X(i) - px); if (dd < bd) { bd = dd; best = i; } }
      return best;
    }
    hit.addEventListener('pointermove', function (e) { show(nearest(e)); });
    hit.addEventListener('pointerleave', hide);
    svg.addEventListener('focus', function () { show(cur >= 0 ? cur : last); });
    svg.addEventListener('blur', hide);
    svg.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowLeft') { show(Math.max(0, (cur < 0 ? last : cur) - 1)); e.preventDefault(); }
      else if (e.key === 'ArrowRight') { show(Math.min(last, (cur < 0 ? 0 : cur) + 1)); e.preventDefault(); }
      else if (e.key === 'Escape') hide();
    });
  };
