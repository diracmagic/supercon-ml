'use strict';
// authors: shared lexical function definitions; no startup side effects.

  const nameSeed = function nameSeed(name) { var h = 7; for (var i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) % 99991; return h; };

  const authorList = function authorList(d) {
    var src = d && Array.isArray(d.authors) && d.authors.length ? d.authors : AUTHORS;
    var out = src.filter(function (a) { return a && typeof a.name === 'string' && a.name.trim(); }).map(function (a) {
      var email = typeof a.email === 'string' ? a.email.trim() : '', name = a.name.trim(), av = a.avatar || {};
      return { name: name, email: EMAIL_OK.test(email) ? email : '', role: typeof a.role === 'string' ? a.role.trim() : '',
        contact: a.contact === true, url: isHttps(a.url) ? a.url : '',
        tree: typeof av.tree === 'number' && isFinite(av.tree) ? Math.abs(Math.round(av.tree)) % 99991 : nameSeed(name) };
    });
    return out;
  };

  const treeKind = function treeKind(seed) {
    var k = 'author-tree-' + seed;
    if (!MINI_DRAW[k]) {
      MINI_DRAW[k] = makeTree(seed);
      MINI_STATIC[k] = 14.95;
      MINI_ALT[k] = 'An animated pencil sketch of a tree in a storm: it is drawn line by line, then bends in the wind under rain and lightning while leaves blow away.';
    }
    return k;
  };


  const copyText = function copyText(text, btn) {
    var label = btn.textContent;
    function done(ok) {
      btn.textContent = ok ? 'Copied' : 'Select the text to copy it';
      setTimeout(function () { btn.textContent = label; }, 1800);
    }
    function fallback() {
      var ta = document.createElement('textarea');
      ta.value = text; ta.setAttribute('readonly', ''); ta.style.position = 'fixed'; ta.style.top = '0'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      var ok = false;
      try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      document.body.removeChild(ta);
      done(ok);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(function () { done(true); }, fallback);
    else fallback();
  };
