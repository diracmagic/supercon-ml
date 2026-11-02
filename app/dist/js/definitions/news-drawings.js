'use strict';
// news-drawings: shared lexical function definitions; no startup side effects.

  const newsArt = function newsArt(n) {
    var tp = list(n.topics), head = String(n.title || ''), body = head + ' ' + String(n.summary || '');
    // Automatic topic tags do not establish a crystal, pressure regime or mechanism.
    // Only neutral motifs with adequate structural context are selected here.
    var materialTopics = ['Hydrides', 'Cuprates', 'Nickelates', 'Iron-based', 'Moiré and 2D', 'Kagome', 'Heavy fermions'];
    if (materialTopics.filter(function (topic) { return tp.indexOf(topic) >= 0; }).length > 1) return 'news-research';
    if (tp.indexOf('Cuprates') >= 0) return 'news-cuprate';
    if (tp.indexOf('Nickelates') >= 0 && /\bbilayer\b|\bdouble[- ]layer\b/i.test(body) && !/\binfinite[- ]layer\b/i.test(body)) return 'news-nickelate';
    if (tp.indexOf('Kagome') >= 0) return 'news-kagome';
    if (tp.indexOf('Moiré and 2D') >= 0 && /\btwist(?:ed|ing)?\b/i.test(body)) return 'news-moire';
    if (tp.indexOf('AI and data') >= 0) return 'news-ai';
    // older feed entries carry "Quantum devices" for any story that mentions quantum computers, so look for a device word too
    if (/qubit|transmon|fluxonium|quantum (processor|computer|computing|information|memory|technolog)|superconducting circuit|circuit QED|single-photon/i.test(head) ||
        /qubit|transmon|fluxonium|circuit QED/i.test(body)) return 'news-qubit';
    return 'news-research';
  };
