'use strict';
// news-drawings: shared lexical function definitions; no startup side effects.

  const newsArt = function newsArt(n) {
    var tp = list(n.topics), head = String(n.title || ''), body = head + ' ' + String(n.summary || '');
    for (var i = 0; i < NEWS_ART.length; i++) if (tp.indexOf(NEWS_ART[i][0]) >= 0) return 'news-' + NEWS_ART[i][1];
    // older feed entries carry "Quantum devices" for any story that mentions quantum computers, so look for a device word too
    if (/qubit|transmon|fluxonium|quantum (processor|computer|computing|information|memory|technolog)|superconducting circuit|circuit QED|single-photon/i.test(head) ||
        /qubit|transmon|fluxonium|circuit QED/i.test(body)) return 'news-qubit';
    return 'news-general';
  };
