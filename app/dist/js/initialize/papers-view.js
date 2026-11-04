'use strict';
// papers-view: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconPapersView = function initializeSuperconPapersView() {


  /* ---------- New papers: curated recent advances and the live feed ---------- */
  PAPERS_URL = 'https://raw.githubusercontent.com/' + REPO + '/' + BRANCH + '/progress/papers.json';

  // Every list opens with five items; Show more adds five at a time.
  paperState = { data: null, at: 0, busy: false, failed: false, src: 'all', topic: 'all', shown: 5, kind: 'all', advShown: 5, aiAdvShown: 5, built: false, newsSrc: 'all', newsShown: 5 };

  PAPER_SOURCES = [['all', 'All'], ['arXiv', 'arXiv'], ['Nature', 'Nature'], ['Science', 'Science'], ['PRL', 'PRL'], ['PRX', 'PRX']];

};
