'use strict';
// content: shared lexical function definitions; no startup side effects.

  const refUrl = function refUrl(r) { return r.u || (r.d ? 'https://doi.org/' + r.d : ''); };

  const refList = function refList(keys, cls) {
    var ol = h('ol', { class: cls || 'refs' });
    (keys || []).forEach(function (k) {
      var r = REFS[k];
      if (!r) return;
      var url = refUrl(r);
      ol.appendChild(h('li', null, url ? h('a', { href: url, text: r.t }) : r.t));
    });
    return ol;
  };

  const renderRefs = function renderRefs(el, keys) {
    clear(el);
    if (!keys || !keys.length) { el.hidden = true; return; }
    el.hidden = false;
    append(el, [h('span', { class: 'refs-title', text: 'References' }), refList(keys)]);
  };

  const nobelUrl = function nobelUrl(y) { return 'https://www.nobelprize.org/prizes/physics/' + y + '/summary/'; };

  const fmtMonth = function fmtMonth(d) { var p = String(d).split('-'); return (p[1] ? MONTHS[+p[1] - 1] + ' ' : '') + p[0]; };

  const recentFor = function recentFor(card) {   // newest first
    return RECENT.map(function (r, i) { return [r, i]; })
      .filter(function (p) { return p[0].cards.indexOf(card) >= 0; })
      .sort(function (a, b) { return a[0].d < b[0].d ? 1 : a[0].d > b[0].d ? -1 : a[1] - b[1]; })
      .map(function (p) { return p[0]; });
  };

  const recentLink = function recentLink(r) {
    var ref = REFS[r.ref];
    if (!ref) return null;
    var url = refUrl(ref);
    return url ? h('a', { href: url, text: ref.t }) : h('span', { text: ref.t });
  };


  const cText = function cText(s, max) { return typeof s === 'string' ? s.replace(/[\u0000-\u001f]/g, ' ').slice(0, max) : ''; };

  const applyContent = function applyContent(d) {
    if (!d || typeof d !== 'object' || !Array.isArray(d.recent)) return false;
    var key = JSON.stringify([d.updated, d.recent.length, list(d.hide).length, Object.keys(d.refs || {}).length, list(d.found).length, list(d.watch).length, list(d.cited_by).length, d.contact || null]);
    if (key === contentState.applied) return false;
    var refs = d.refs && typeof d.refs === 'object' ? d.refs : {};
    Object.keys(refs).slice(0, 200).forEach(function (k) {
      var r = refs[k];
      if (!/^[a-z0-9_-]{2,40}$/i.test(k) || !r || typeof r.t !== 'string') return;
      var doi = typeof r.d === 'string' && /^10\.\d{4,9}\/\S+$/.test(r.d) ? r.d : '';
      var url = isHttps(r.u) ? r.u : '';
      if (doi || url) REFS[k] = doi ? { t: cText(r.t, 220), d: doi } : { t: cText(r.t, 220), u: url };
    });
    var hide = {};
    list(d.hide).forEach(function (h) { if (typeof h === 'string') hide[h] = 1; });
    var extra = d.recent.slice(0, 120).filter(function (r) {
      return r && typeof r.h === 'string' && typeof r.x === 'string' && /^\d{4}(-\d{2})?$/.test(String(r.d || '')) &&
        CONTENT_KINDS[r.k] && Array.isArray(r.cards) && typeof r.ref === 'string' && REFS[r.ref];
    }).map(function (r) {
      return { d: r.d, k: r.k, ref: r.ref, h: cText(r.h, 180), x: cText(r.x, 900), live: true,
        cards: r.cards.filter(function (c) { return typeof c === 'string' && c.length < 30; }).slice(0, 5) };
    });
    var seen = {};
    extra.forEach(function (r) { seen[r.ref] = 1; });
    var merged = extra.concat(RECENT_BUILTIN.filter(function (r) { return !hide[r.ref] && !seen[r.ref]; }));
    RECENT.length = 0;
    Array.prototype.push.apply(RECENT, merged);
    // superconductors found with AI: a valid list in content.json replaces the built-in one
    function aiRows(rows) {
      return list(rows).slice(0, 40).map(function (r) {
        var refs = !r ? [] : (Array.isArray(r.refs) ? r.refs : [r.ref]).filter(function (k) { return typeof k === 'string' && REFS[k]; }).slice(0, 3);
        if (!r || typeof r.h !== 'string' || typeof r.x !== 'string' || typeof r.tc !== 'string' || typeof r.m !== 'string' || !/^\d{4}$/.test(String(r.d || '')) || !refs.length) return null;
        return { d: String(r.d), refs: refs, h: cText(r.h, 120), tc: cText(r.tc, 60), m: cText(r.m, 40), x: cText(r.x, 900) };
      }).filter(Boolean);
    }
    var found = aiRows(d.found), watch = aiRows(d.watch);
    AI_FOUND.length = 0;
    Array.prototype.push.apply(AI_FOUND, found.length ? found : AI_FOUND_BUILTIN);
    if (Array.isArray(d.watch)) { AI_WATCH.length = 0; Array.prototype.push.apply(AI_WATCH, watch); }
    CITED_BY.length = 0;
    list(d.cited_by).slice(0, 100).forEach(function (r) {
      if (!r || typeof r.t !== 'string' || !r.t.trim()) return;
      var doi = typeof r.d === 'string' && /^10\.\d{4,9}\/\S+$/.test(r.d) ? r.d : '', url = isHttps(r.u) ? r.u : '';
      CITED_BY.push({ t: cText(r.t, 300), url: doi ? 'https://doi.org/' + doi : url, y: /^\d{4}(-\d{2}){0,2}$/.test(String(r.y || '')) ? String(r.y) : '',
        what: cText(typeof r.what === 'string' ? r.what : '', 200) });
    });
    var ct = d.contact && typeof d.contact === 'object' ? d.contact : {};
    CONTACT = ct.service === 'web3forms' && typeof ct.key === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(ct.key) ? { service: 'web3forms', key: ct.key } :
      ct.service === 'formspree' && typeof ct.form === 'string' && /^[a-z0-9]{6,16}$/i.test(ct.form) ? { service: 'formspree', form: ct.form } : null;
    contentState.applied = key;
    contentState.updated = typeof d.updated === 'string' ? d.updated : '';
    return true;
  };

  const contentChanged = function contentChanged() {
    if (paperState.built) renderAdvances();
    if (learn.built) { learn.built = false; if (view === 'learn') { buildLearn(); miniKick(); } }
    if (view === 'authors') renderAuthors();
  };

  const loadContent = function loadContent(force) {
    if (contentState.busy || (!force && Date.now() - contentState.at < 10 * 60 * 1000)) return Promise.resolve();
    contentState.busy = true;
    return getJSON(CONTENT_URL).then(function (d) {
      contentState.at = Date.now();
      if (applyContent(d)) { store.set('content', JSON.stringify(d)); contentChanged(); }
    }, function () { /* keep the built-in and cached content */ }).then(function () { contentState.busy = false; });
  };
