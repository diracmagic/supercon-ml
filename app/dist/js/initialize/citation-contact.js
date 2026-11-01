'use strict';
// citation-contact: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconCitationContact = function initializeSuperconCitationContact() {


  /* ---------- Cite: how to cite the project, and the published work that cites it ----------
     This view showed the authors until version 0.3.7; who they are stays hidden for now (AUTHORS and progress.json
     "authors" are kept for later). The citation names the project, and every "tell us" link in the app leads to the
     message form below, which shows neither a name nor an address. */
  authorsState = { sig: '' };

  CITE_TITLE = 'supercon-ml: finding superconductors with AI-designed models';

  /* ---------- Write to us: a message form that delivers to the project's inbox without showing its address ----------
     It sends once progress/content.json names a delivery service ("contact"); until that loads, the card says so. A draft
     survives a re-render, and every "tell us" link in the app opens the form with its topic chosen. */
  CONTACT_TOPICS = [
    ['question', 'A question or an idea', 'Your question or idea'],
    ['candidate', 'An earlier report of a candidate', 'Which material, and where was it reported or predicted before? A DOI or a link helps.'],
    ['citation', 'A work that cites supercon-ml', 'The title of the work, and a DOI or a link'],
    ['problem', 'A problem in the app', 'What happened, and where: the desktop app or the web app?'],
    ['experiment', 'Measuring one of our candidates', 'Which candidate, and what you could do: grow a sample, measure resistivity or susceptibility, ...'],
    ['collab', 'A collaboration', 'What you have in mind'],
    ['other', 'Something else', '']];

  contactState = { busy: false, draft: { topic: 'question', name: '', email: '', msg: '' }, status: '' };

  CONTACT_SERVICE = { web3forms: 'Web3Forms', formspree: 'Formspree' };

  /* ---------- where the data and software come from, and under which licences ---------- */
  CC_BY = 'https://creativecommons.org/licenses/by/4.0/';

  LICENCES = [
    { name: 'Alexandria', url: 'https://alexandria.icams.rub.de/', use: 'about 8,250 DFT electron–phonon calculations; Storm learns from the 7,600 that pass our checks',
      lic: 'CC BY 4.0', licUrl: CC_BY, cite: [['T. F. T. Cerqueira et al., Adv. Mater. 36, 2307085 (2024)', '10.1002/adma.202307085'], ['T. Cavignac et al., J. Phys. Mater. 9, 025014 (2026)', '10.1088/2515-7639/ae6620']] },
    { name: 'JARVIS-DFT', url: 'https://jarvis.nist.gov/', use: 'about 1,000 electron–phonon calculations kept aside as Storm’s locked test set',
      lic: 'NIST open licence', licUrl: 'https://www.nist.gov/open/license', cite: [['K. Choudhary & K. Garrity, npj Comput. Mater. 8, 244 (2022)', '10.1038/s41524-022-00933-1']] },
    { name: '3DSC', url: 'https://github.com/aimat-lab/3DSC', use: 'measured Tc for Hurricane and Storm 3.0: the SuperCon database (NIMS) matched to Materials Project crystal structures',
      lic: 'CC BY 4.0', licUrl: CC_BY, cite: [['T. Sommer et al., Sci. Data 10, 816 (2023)', '10.1038/s41597-023-02721-y'], ['A. Jain et al., APL Mater. 1, 011002 (2013)', '10.1063/1.4812323']] },
    { name: 'arXiv', url: 'https://arxiv.org/', use: 'titles, authors and abstracts of new preprints, through the arXiv API',
      lic: 'CC0 metadata', licUrl: 'https://info.arxiv.org/help/api/tou.html' },
    { name: 'Crossref and journal feeds', url: 'https://www.crossref.org/', use: 'titles, authors and links of journal papers; abstracts stay with their publishers, so we show only their first sentence',
      lic: 'metadata terms', licUrl: 'https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-metadata-license-information/' },
    { name: 'News sites', use: 'headlines and a short summary from each site’s public feed, always linking to the full story' }
  ];

};
