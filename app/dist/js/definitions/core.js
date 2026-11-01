'use strict';
// core: shared lexical function definitions; no startup side effects.


  /* ---------- helpers ---------- */
  const $ = function $(sel) { return document.querySelector(sel); };

  const clear = function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); };

  const list = function list(x) { return Array.isArray(x) ? x : []; };

  const h = function h(tag, attrs) {
    var el = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      var v = attrs[k];
      if (v === null || v === undefined || v === false) return;
      if (k === 'class') el.className = v;
      else if (k === 'text') el.textContent = v;
      else if (k.slice(0, 2) === 'on' && typeof v === 'function') el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? '' : String(v));
    });
    append(el, Array.prototype.slice.call(arguments, 2));
    return el;
  };

  const append = function append(el, kids) {
    kids.forEach(function (kid) {
      if (kid === null || kid === undefined || kid === false) return;
      if (Array.isArray(kid)) append(el, kid);
      else el.appendChild(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    });
  };

  const s = function s(tag, attrs, text) {
    var el = document.createElementNS(SVGNS, tag);
    Object.keys(attrs || {}).forEach(function (k) { el.setAttribute(k, attrs[k]); });
    if (text !== undefined) el.textContent = text;
    return el;
  };

  const glyph = function glyph(kind, cls) {
    var span = h('span', { class: cls });
    span.innerHTML = G[kind] || '';
    return span;
  };

  const t = function t(key, vars) {
    var str = (STR[lang] && STR[lang][key] !== undefined) ? STR[lang][key] : (STR.en[key] !== undefined ? STR.en[key] : key);
    return vars ? str.replace(/\{(\w+)\}/g, function (_, k) { return vars[k] !== undefined ? vars[k] : ''; }) : str;
  };

  const L = function L(v) {
    if (v === null || v === undefined) return '';
    if (typeof v === 'string' || typeof v === 'number') return String(v);
    return v[lang] || v.en || v.zh || '';
  };

  const locale = function locale() { return 'en-US'; };

  const isHttps = function isHttps(u) { return typeof u === 'string' && /^https:\/\/\S+$/.test(u); };


  const parseDate = function parseDate(v) {
    if (!v) return null;
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(v);
    if (m) return new Date(+m[1], +m[2] - 1, +m[3]);
    var d = new Date(v);
    return isNaN(d.getTime()) ? null : d;
  };

  const fmt = function fmt(d, opts) { try { return new Intl.DateTimeFormat(locale(), opts).format(d); } catch (e) { return d.toLocaleString(); } };

  const fmtDay = function fmtDay(d) { return fmt(d, { month: 'short', day: 'numeric' }); };

  const fmtStamp = function fmtStamp(d) { return fmt(d, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }); };

  const fmtTime = function fmtTime(d) { return fmt(d, { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }); };

  const rel = function rel(d) {
    var sec = (d.getTime() - Date.now()) / 1000;
    var a = Math.abs(sec);
    var unit, n;
    if (a < 45) { unit = 'second'; n = 0; }
    else if (a < 3600) { unit = 'minute'; n = Math.round(sec / 60); }
    else if (a < 86400) { unit = 'hour'; n = Math.round(sec / 3600); }
    else if (a < 86400 * 30) { unit = 'day'; n = Math.round(sec / 86400); }
    else return fmt(d, { year: 'numeric', month: 'short', day: 'numeric' });
    if (window.Intl && Intl.RelativeTimeFormat) {
      return new Intl.RelativeTimeFormat(locale(), { numeric: 'auto' }).format(n, unit);
    }
    return fmtStamp(d);
  };

  const daysUntil = function daysUntil(d) {
    var now = new Date();
    var a = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    var b = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    return Math.round((b - a) / 86400000);
  };

  const fmtVal = function fmtVal(v) { return typeof v === 'number' ? String(Number(v.toPrecision(3))) : String(v); };

  const fmtTick = function fmtTick(v) { return String(Number(v.toFixed(3))); };

  const niceStep = function niceStep(max, count) {
    var raw = max / count;
    var p = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10));
    var f = raw / p;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
  };


  const openExternal = function openExternal(url) {
    if (!isHttps(url) && !/^mailto:[^\s]+$/i.test(url)) return;
    var T = window.__TAURI__;
    var I = window.__TAURI_INTERNALS__;
    try {
      if (T && T.opener && typeof T.opener.openUrl === 'function') { Promise.resolve(T.opener.openUrl(url)).catch(function () {}); return; }
      if (T && T.core && typeof T.core.invoke === 'function') { Promise.resolve(T.core.invoke('plugin:opener|open_url', { url: url })).catch(function () {}); return; }
      if (I && typeof I.invoke === 'function') { Promise.resolve(I.invoke('plugin:opener|open_url', { url: url })).catch(function () {}); return; }
    } catch (e) { /* fall through to the browser */ }
    window.open(url, '_blank', 'noopener');
  };


  /* ---------- data ---------- */
  const getJSON = function getJSON(url, opts) {
    opts = opts || {};
    var ctl = window.AbortController ? new AbortController() : null;
    var timer = setTimeout(function () { if (ctl) ctl.abort(); }, opts.timeout || 12000);
    return fetch(url, { signal: ctl ? ctl.signal : undefined, headers: opts.headers, cache: 'no-cache' })
      .then(function (r) {
        if (!r.ok) { var err = new Error('HTTP ' + r.status); err.status = r.status; err.headers = r.headers; throw err; }
        return r.json();
      })
      .then(function (v) { clearTimeout(timer); return v; }, function (err) { clearTimeout(timer); throw err; });
  };

  const valid = function valid(d) { return d && typeof d === 'object' && Array.isArray(d.stages); };


  const loadBundled = function loadBundled() {
    var inline = document.getElementById('bundled-data');
    var text = inline ? inline.textContent.trim() : '';
    if (text) {
      try {
        var d0 = JSON.parse(text);
        if (valid(d0) && !state.data) state.data = d0;
        return Promise.resolve();
      } catch (e) { /* fall back to the bundled file */ }
    }
    return getJSON('progress.json', { timeout: 4000 }).then(function (d) {
      if (valid(d) && !state.data) state.data = d;
    }, function () { /* no bundled copy */ });
  };

  // Resolves to 'ok', 'missing' (repository or file not published yet) or 'offline'.
  const loadLive = function loadLive() {
    return getJSON(DATA_URL).then(function (d) {
      if (!valid(d)) return 'offline';
      state.data = d;
      return 'ok';
    }, function (err) { return err && err.status === 404 ? 'missing' : 'offline'; });
  };

  const classify = function classify(err) {
    var st = err && err.status;
    if (st === 404) return { kind: 'missing' };
    if (st === 403 || st === 429) {
      var hd = err.headers;
      var remaining = hd ? hd.get('x-ratelimit-remaining') : null;
      var reset = hd ? Number(hd.get('x-ratelimit-reset')) : 0;
      if (st === 429 || remaining === '0') return { kind: 'rate', until: reset ? reset * 1000 : Date.now() + 15 * 60 * 1000 };
    }
    return { kind: 'error' };
  };

  const loadGitHub = function loadGitHub() {
    if (state.gh && state.gh.kind === 'rate' && Date.now() < state.gh.until) return Promise.resolve();
    var opts = { headers: { Accept: 'application/vnd.github+json' } };
    return Promise.all([
      getJSON(API + '/actions/runs?per_page=5', opts).then(function (v) { return { ok: v }; }, function (e) { return { err: e }; }),
      getJSON(API + '/commits?per_page=5', opts).then(function (v) { return { ok: v }; }, function (e) { return { err: e }; })
    ]).then(function (res) {
      var problem = null;
      if (res[0].ok) state.runs = list(res[0].ok.workflow_runs);
      else problem = classify(res[0].err);
      if (res[1].ok) state.commits = list(res[1].ok);
      else if (res[1].err && res[1].err.status === 409) state.commits = []; // empty repository
      else problem = problem || classify(res[1].err);
      state.gh = problem;
    });
  };

  const refreshAll = function refreshAll() {
    if (state.busy) return Promise.resolve();
    state.busy = true;
    setBusy(true);
    return Promise.all([loadLive(), loadGitHub()]).then(function (res) {
      state.live = res[0];
      state.loaded = true;
      state.checkedAt = new Date();
    }).catch(function () { /* keep the previous render */ }).then(function () {
      state.busy = false;
      setBusy(false);
      render();
    });
  };
