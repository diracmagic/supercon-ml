'use strict';
// citation-contact: shared lexical function definitions; no startup side effects.

  const modelMethodSources = function modelMethodSources() {
    return [
  {
    "id": "roter2022-clustering",
    "title": "Clustering superconductors using unsupervised machine learning",
    "citation": "B. Roter et al. (2022)",
    "url": "https://doi.org/10.1016/j.physc.2022.1354078",
    "scope": "Storm7, Hurricane8",
    "relation": "direct superconductivity clustering precedent",
    "prior": "Clusters superconductors using composition-based k-means, hierarchical and Gaussian-mixture methods, self-organizing maps and other clustering; discusses visualization and physically meaningful groupings.",
    "ours": "Our 16 KMeans centers are fitted only on eligible training physical features, then transformed into Gaussian RBF similarities. Storm7 uses geometry; H8 uses its allowed physical main effects. We test added predictive value against unchanged heads, not whether clusters prove mechanisms. No identical published implementation is claimed."
  },
  {
    "id": "roter2020-pca",
    "title": "Predicting new superconductors and their critical temperatures using machine learning",
    "citation": "B. Roter & S. V. Dordevic (2020)",
    "url": "https://doi.org/10.1016/j.physc.2020.1353689",
    "scope": "Storm historical PCA, Storm6 R4, Hurricane7 R2",
    "relation": "direct superconductivity representation-learning precedent",
    "prior": "Forms element-composition vectors, applies SVD/PCA, and uses the resulting representation in supervised superconductivity classification and critical-temperature regression.",
    "ours": "Our representations compress geometry or historical MACE descriptors instead of composition-only element vectors. Preprocessing and PCA are refitted inside the relevant train split. H7 R2 is observed-positive/unlabeled parent ranking, not measured Tc regression."
  },
  {
    "id": "stanev2018-composition",
    "title": "Machine learning modeling of superconducting critical temperature",
    "citation": "Valentin Stanev et al. (2018)",
    "url": "https://doi.org/10.1038/s41524-018-0085-8",
    "scope": "Hurricane4, Radar, Storm composition baseline",
    "relation": "composition/classification-regression and family-specific model precedent",
    "prior": "Uses composition-derived descriptors for classification and Tc regression, including separate cuprate, iron-based and low-Tc models, and integrates classification/regression for database screening.",
    "ours": "Radar learns a 3DSC family-label routing proxy rather than the paper's above/below 10 K label; it does not establish pairing mechanism. Hurricane4 adds structure features and abstention. Neither reproduces this paper's model or performance."
  },
  {
    "id": "konno2021-extrapolation",
    "title": "Deep learning model for finding new superconductors",
    "citation": "Tomohiko Konno et al. (2021)",
    "url": "https://doi.org/10.1103/PhysRevB.103.014509",
    "scope": "Hurricane4 LOFO, Hurricane7, Hurricane8, Radar LOFO",
    "relation": "same-field extrapolation benchmark, not adopted architecture",
    "prior": "Encodes compositions as a periodic-table representation and retrospectively tests whether pre-2008 data can retrieve later iron-based superconductors. Also proposes synthetic non-superconductor augmentation.",
    "ours": "H7/H8 remove the held family and all of its chemical systems; earlier H4/Radar reports use family holdout. These are not the same temporal backtest. The inspected families are exploratory, not a new blind test. H7/H8 retain unlabeled parents as U, not verified negatives; neither test demonstrates an experimental discovery."
  },
  {
    "id": "choudhary2022-components",
    "title": "Designing high-TC superconductors with BCS-inspired screening, density functional theory, and deep-learning",
    "citation": "Kamal Choudhary & Kevin Garrity (2022)",
    "url": "https://doi.org/10.1038/s41524-022-00933-1",
    "scope": "Storm, Storm6 R1/R3/R4, Storm component baselines",
    "relation": "direct component-prediction precedent and JARVIS data context",
    "prior": "Compares direct DFT Tc prediction, predicted lambda and omega_log followed by McMillan-Allen-Dynes, and predicted Eliashberg spectra. Uses ALIGNN and handcrafted CFID descriptors.",
    "ours": "Our CPU challengers use histogram gradient boosting with composition/geometry and training-only PCA; the main labels are recomputed Alexandria simplified Allen-Dynes values. We neither train ALIGNN here nor infer measured superconductivity from a computed Tc. Published MAEs use different datasets/splits."
  },
  {
    "id": "xie2022-cluster-validation",
    "title": "Machine learning of superconducting critical temperature from Eliashberg theory",
    "citation": "S. R. Xie et al. (2022)",
    "url": "https://doi.org/10.1038/s41524-021-00666-7",
    "scope": "Storm validation, Hurricane LOFO context",
    "relation": "direct superconductivity leave-cluster-out precedent; theory benchmark, not formula adoption",
    "prior": "Learns corrections to McMillan/Allen-Dynes from spectral moments and Eliashberg targets. Uses k-means-based leave-cluster-out validation and nested validation for predictive models.",
    "ours": "Our chemically grouped/held-family tests differ from spectral-feature clusters; our inputs are composition/geometry and the Storm target remains simplified Allen-Dynes. We have not implemented their SISSO equation or numerical Eliashberg solver, so cannot claim its physics or accuracy."
  },
  {
    "id": "sommer2023-3dsc",
    "title": "3DSC - a dataset of superconductors including crystal structures",
    "citation": "Timo Sommer et al. (2023)",
    "url": "https://doi.org/10.1038/s41597-023-02721-y",
    "scope": "Hurricane4, Hurricane7, Hurricane8, Radar",
    "relation": "directly reused dataset plus structure/grouped-validation precedent",
    "prior": "Matches SuperCon entries to crystal structures, tests composition and structure descriptors with gradient boosting, and partitions train/test by chemical system.",
    "ours": "Our features are not their MAGPIE+DSOAP pipeline. H7/H8 aggregate matched parents and rank recorded-positive descendants against unlabeled parents; their target is not a calibrated superconductivity probability. Structure matches remain a provenance limitation, not measured sample identity."
  },
  {
    "id": "gibson2026-ensemble",
    "title": "Developing a complete AI-accelerated workflow for superconductor discovery",
    "citation": "Jason B. Gibson et al. (2026)",
    "url": "https://doi.org/10.1038/s41524-026-01964-8",
    "scope": "Storm ensemble context, Hurricane screening fold-disagreement context",
    "relation": "superconductivity ensemble/screening precedent, not reused BEE-NET implementation",
    "prior": "Uses bootstrapped equivariant-network ensembles to predict Eliashberg spectra, followed by staged computational screening and experiments on selected materials.",
    "ours": "Our five training-fold candidate scores are not BEE-NET bootstrap models; their spread is descriptive disagreement, not a confidence or conformal interval. Storm6/7 conformal bands are separate. We do not reproduce the paper's network, experiments or discovery claims."
  },
  {
    "id": "allen1975-formula",
    "title": "Transition temperature of strong-coupled superconductors reanalyzed",
    "citation": "P. B. Allen & R. C. Dynes (1975)",
    "url": "https://doi.org/10.1103/PhysRevB.12.905",
    "scope": "Storm, Storm6, Storm7",
    "relation": "direct physics-formula foundation; not an AI precedent",
    "prior": "Derives an approximate Tc relation from Eliashberg theory including logarithmic phonon frequency and strong-coupling/shape corrections.",
    "ours": "We do not implement the complete strong-coupling corrections or solve Eliashberg equations. Those approximations define the DFT-derived target; they are not experimental measurements or a new learned law."
  },
  {
    "id": "lei2018-conformal",
    "title": "Distribution-Free Predictive Inference for Regression",
    "citation": "Jing Lei et al. (2018)",
    "url": "https://doi.org/10.1080/01621459.2017.1307116",
    "scope": "Storm6, Storm7, Storm interval context",
    "relation": "general statistical method foundation; NOT a superconductivity-specific precedent",
    "prior": "Develops and compares full/split conformal predictive inference and related jackknife methods, separating regression fitting from calibration.",
    "ours": "Storm6/7 calibrate maximum log-scale residual per chemical system, requiring exchangeability at the system level. This paper alone does not validate our grouped adaptation or guarantee coverage under family/database shift. Five-fold candidate min/max spread is not this method, nor jackknife+."
  },
  {
    "id": "xie2018-cgcnn",
    "title": "Crystal Graph Convolutional Neural Networks for an Accurate and Interpretable Prediction of Material Properties",
    "citation": "Tian Xie & Jeffrey C. Grossman (2018)",
    "url": "https://doi.org/10.1103/PhysRevLett.120.145301",
    "scope": "Storm graph branch, ml/gnn.py, ml/gnn2.py",
    "relation": "direct architecture attribution; general crystal-property ML, not a superconductivity-discovery paper",
    "prior": "Introduces periodic crystal graphs, convolutional updates from neighboring atoms/bonds, gated nonlinear message functions and pooled crystal representations for DFT-property prediction.",
    "ours": "Our JAX implementation restricts each atom to 12 nearest neighbors within 8 angstrom, uses Gaussian edge distances and supervised electron-phonon targets. Later hybrid variants add composition/structure/physics descriptors to the readout. This is an adaptation, not a reproduction of their code, benchmark or claimed accuracy; these settings are not asserted to be uniquely novel."
  },
  {
    "id": "batatia2025-mace-mp",
    "title": "A foundation model for atomistic materials chemistry",
    "citation": "Ilyes Batatia et al. (2025)",
    "url": "https://doi.org/10.1063/5.0297006",
    "scope": "Hurricane6 M1, historical Storm frozen-MACE descriptor experiments",
    "relation": "direct pretrained checkpoint reuse; interatomic-potential paper, not a supervised superconductivity predictor",
    "prior": "Develops the MACE-MP-0 family of pretrained interatomic potentials for energies/forces and atomistic simulation across diverse chemical systems.",
    "ours": "The potential was not trained to predict superconductivity. H6 is a report-only LOFO descriptor-transfer experiment and was not adopted. Its pinned 2023 checkpoint must not be conflated with the journal paper's newer 0b3 evaluations; neither force accuracy nor clustering establishes Tc or pairing mechanism."
  }
];
  };

  const modelMethodsCard = function modelMethodsCard() {
    var entries = h('ol', { class: 'cite-list method-sources' });
    modelMethodSources().forEach(function (r) {
      entries.appendChild(h('li', { id: 'method-' + r.id },
        h('p', { class: 'method-scope', text: r.scope }),
        h('p', null, h('a', { href: r.url, text: r.title }), ' · ' + r.citation),
        h('p', { class: 'method-relation', text: r.relation }),
        h('p', null, h('b', { text: 'Prior work. ' }), r.prior),
        h('p', null, h('b', { text: 'Our implementation and differences. ' }), r.ours)));
    });
    return h('section', { class: 'card cite-card', id: 'model-methods' },
      cardHead('Model methods, sources & differences', 'Published precedents and foundations for Storm, Hurricane and Radar.'),
      h('p', { class: 'note', text: 'Shared algorithms and datasets are credited below. Related prior work identified in this audit is distinguished from directly reused data or model weights. Method overlap does not imply that we reproduced a published model or its reported accuracy.' }),
      h('p', { class: 'note' }, 'The KMeans–RBF prototype comparison is an experimental extension: its first frozen Storm and Hurricane tests showed no stable gain. Current released models are unchanged. ',
        h('a', { href: 'https://github.com/diracmagic/supercon-ml/pull/17', text: 'Audited experiment and results' })),
      entries);
  };

  const citeYear = function citeYear() { var m = /^(\d{4})/.exec(String((state.data && state.data.updated) || '')); return m ? m[1] : '2026'; };

  const citeToday = function citeToday() { var d = new Date(); return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); };

  const citeText = function citeText() { return 'The supercon-ml project (' + citeYear() + '). ' + CITE_TITLE + '. GitHub repository, ' + REPO_URL + ' (accessed ' + citeToday() + ').'; };

  const citeBib = function citeBib() {
    return '@misc{supercon_ml,\n  author       = {{The supercon-ml project}},\n  title        = {{supercon-ml}: finding superconductors with {AI}-designed models},\n' +
      '  year         = {' + citeYear() + '},\n  howpublished = {GitHub repository, \\url{' + REPO_URL + '}},\n  note         = {Accessed ' + citeToday() + '}\n}';
  };

  const renderAuthors = function renderAuthors() {
    var el = $('#authors');
    if (!el) return;
    var ex = candRows(state.data && state.data.screen).rows[0], sc = state.data && state.data.screen;
    var sig = JSON.stringify([citeYear(), citeToday(), CITED_BY.map(function (c) { return c.t + c.url + c.y; }).join('|'), ex ? candId(ex) : '', sc && sc.round, CONTACT]);
    if (sig === authorsState.sig && el.firstChild) return;
    authorsState.sig = sig;
    clear(el);
    miniPrune();
    var text = citeText(), bib = citeBib();
    var copyCite = h('button', { class: 'btn small', type: 'button' }, 'Copy the citation');
    copyCite.addEventListener('click', function () { copyText(text, copyCite); });
    var copyBib = h('button', { class: 'btn small', type: 'button' }, 'Copy BibTeX');
    copyBib.addEventListener('click', function () { copyText(bib, copyBib); });
    var exl = ex && ex.listed && /^\d{4}-\d{2}-\d{2}$/.test(String(ex.listed.date)) ? ex.listed : null;
    var example = ex ? ', for example: ' + ex.formula + ', Screening round ' + ((exl && exl.round) || (sc && sc.round) || 1) + (ex.id ? ', ' + ex.id : '') + (exl ? ', first listed ' + fmtDayISO(exl.date) : '') : '';
    var cite = h('section', { class: 'card cite-card' },
      cardHead('How to cite', 'If you use our models, predictions, candidate list or code, please cite the project.'),
      h('p', { class: 'cite-text', id: 'cite-text' }, text),
      h('pre', { class: 'cite-bib', id: 'cite-bib' }, bib),
      h('div', { class: 'cite-actions' }, copyCite, copyBib),
      richText(h('p', { class: 'note' }, ''), 'To cite one of our candidate superconductors, also give its name, the screening round that first listed it, its JARVIS ID and the date' + example +
        '. Every screening round is dated in the repository, so its history records when each candidate was first proposed.'),
      h('p', { class: 'note' }, 'GitHub’s “Cite this repository” button on the ', h('a', { href: REPO_URL, text: 'repository page' }), ' gives the same citation. Please also cite the data we build on, listed below.'));
    var cited = h('section', { class: 'card cite-card', id: 'cited-by' },
      cardHead('Cited by', CITED_BY.length ? 'Published work that cites supercon-ml, newest first.' : 'Published work that cites supercon-ml is listed here.'));
    if (CITED_BY.length) {
      var ol = h('ol', { class: 'cite-list' });
      CITED_BY.forEach(function (c) {
        ol.appendChild(h('li', null, c.url ? h('a', { href: c.url, text: c.t }) : h('span', { text: c.t }), c.y ? ' (' + c.y + ')' : '',
          c.what ? h('div', { class: 'dt-cell-sub', text: c.what }) : null));
      });
      cited.appendChild(ol);
    } else cited.appendChild(h('p', { class: 'cite-none', text: 'No published work cites supercon-ml yet.' }));
    cited.appendChild(h('p', { class: 'note' }, 'Cited supercon-ml? ', contactLink('Tell us', 'citation'), ' and we will list your work here.'));
    append(el, [cite, modelMethodsCard(), cited, contactCard(), licencesCard(),
      h('p', { class: 'note cite-foot' }, 'Code, data and every training run are public on ', h('a', { href: REPO_URL, text: 'GitHub' }),
        '. Questions, ideas or a problem in the app? ', contactLink('Write to us', 'question'), '.')]);
  };

  const contactTopic = function contactTopic(k) { return CONTACT_TOPICS.filter(function (t) { return t[0] === k; })[0] || CONTACT_TOPICS[0]; };

  // a link anywhere in the app that opens the message form on the Cite view
  const contactLink = function contactLink(text, topic) {
    return h('a', { href: '#contact-card', class: 'ct-go', onclick: function (e) { e.preventDefault(); contactGo(topic); } }, text);
  };

  const contactGo = function contactGo(topic) {
    var dr = contactState.draft;
    if (topic) dr.topic = contactTopic(topic)[0];
    contactState.status = '';
    if (view !== 'authors') setView('authors'); else renderAuthors();
    var card = $('#contact-card'), sel = $('#ct-topic'), msg = $('#ct-msg'), st = $('#contact-card .ct-status');
    if (sel) { sel.value = dr.topic; contactHint(); }
    if (st) st.textContent = '';
    if (!card) return;
    card.scrollIntoView({ block: 'start', behavior: motionOK() ? 'smooth' : 'auto' });
    // on a phone, focusing the box would open the keyboard before the reader has seen the form
    if (msg && window.matchMedia && window.matchMedia('(pointer: fine)').matches) { try { msg.focus({ preventScroll: true }); } catch (err) { msg.focus(); } }
  };

  const contactHint = function contactHint() {
    var msg = $('#ct-msg');
    if (msg) msg.setAttribute('placeholder', contactTopic(contactState.draft.topic)[2]);
  };

  const contactCard = function contactCard() {
    var head = cardHead('Write to us', 'Questions, ideas, a correction or a collaboration: your message goes straight to the project’s inbox.');
    if (!CONTACT) {
      return h('section', { class: 'card', id: 'contact-card' }, head,
        h('p', { class: 'note' }, 'The message form loads with the app’s online content, which has not arrived yet. ',
          h('button', { class: 'btn small', type: 'button', onclick: function () { loadContent(true); } }, 'Try again')));
    }
    var dr = contactState.draft;
    var topic = h('select', { id: 'ct-topic' });
    CONTACT_TOPICS.forEach(function (t) { topic.appendChild(h('option', { value: t[0], text: t[1] })); });
    var name = h('input', { type: 'text', id: 'ct-name', maxlength: '100', autocomplete: 'name' });
    var mail = h('input', { type: 'email', id: 'ct-email', maxlength: '200', autocomplete: 'email', inputmode: 'email' });
    var msg = h('textarea', { id: 'ct-msg', rows: '5', maxlength: '4000', placeholder: contactTopic(dr.topic)[2] });
    topic.value = contactTopic(dr.topic)[0]; name.value = dr.name; mail.value = dr.email; msg.value = dr.msg;
    topic.addEventListener('change', function () { dr.topic = topic.value; msg.setAttribute('placeholder', contactTopic(dr.topic)[2]); });
    [['name', name], ['email', mail], ['msg', msg]].forEach(function (p) { p[1].addEventListener('input', function () { dr[p[0]] = p[1].value; }); });
    var trap = h('input', { type: 'checkbox', class: 'ct-trap', tabindex: '-1', autocomplete: 'off', 'aria-hidden': 'true' });
    var status = h('p', { class: 'ct-status', role: 'status', 'aria-live': 'polite', text: contactState.status });
    var send = h('button', { class: 'btn primary', type: 'submit', disabled: contactState.busy }, 'Send');
    var form = h('form', { class: 'ct-form', novalidate: true },
      h('label', { for: 'ct-topic' }, 'About'), topic,
      h('label', { for: 'ct-name' }, 'Your name ', h('span', { class: 'ct-opt', text: '(optional)' })), name,
      h('label', { for: 'ct-email' }, 'Your email ', h('span', { class: 'ct-opt', text: '(optional, so that we can reply)' })), mail,
      h('label', { for: 'ct-msg' }, 'Message'), msg, trap,
      h('div', { class: 'ct-actions' }, send, status));
    form.addEventListener('submit', function (e) { e.preventDefault(); contactSend({ form: form, topic: topic, name: name, mail: mail, msg: msg, trap: trap, status: status, send: send }); });
    return h('section', { class: 'card', id: 'contact-card' }, head, form,
      h('p', { class: 'note' }, 'We use your email address only to reply. ' + CONTACT_SERVICE[CONTACT.service] + ' delivers the message; the inbox address is not shown here.'));
  };

  const contactSay = function contactSay(f, text) { contactState.status = text; f.status.textContent = text; };

  const contactSend = function contactSend(f) {
    var c = CONTACT, text = f.msg.value.trim(), email = f.mail.value.trim(), name = f.name.value.trim(), about = contactTopic(f.topic.value)[1];
    if (!c || contactState.busy) return;
    if (f.trap.checked) { contactSay(f, 'Sent. Thank you!'); return; }   // a robot ticked the hidden box: drop it quietly
    if (text.length < 5) { contactSay(f, 'Please write a message first.'); f.msg.focus(); return; }
    if (email && !EMAIL_OK.test(email)) { contactSay(f, 'That email address does not look right.'); f.mail.focus(); return; }
    contactState.busy = true;
    f.send.disabled = true;
    contactSay(f, 'Sending…');
    var subject = 'supercon-ml: ' + about.charAt(0).toLowerCase() + about.slice(1);
    var body = 'About: ' + about + '\n\n' + text + '\n\n(sent from the supercon-ml ' + (isDesktop() ? 'desktop' : 'web') + ' app, version ' + APP_VERSION + ')';
    var req = c.service === 'web3forms' ?
      { url: 'https://api.web3forms.com/submit', body: { access_key: c.key, subject: subject, from_name: 'supercon-ml app', name: name || 'Anonymous', email: email || undefined, message: body, botcheck: false } } :
      { url: 'https://formspree.io/f/' + c.form, body: { _subject: subject, name: name || 'Anonymous', email: email || undefined, message: body } };
    fetch(req.url, { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify(req.body) })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { return { ok: r.ok && (j.success === true || j.ok === true), j: j }; }); })
      .then(function (res) {
        if (res.ok) {
          contactState.draft = { topic: contactState.draft.topic, name: '', email: '', msg: '' };
          f.name.value = ''; f.mail.value = ''; f.msg.value = '';
          contactSay(f, 'Sent. Thank you!');
        } else contactSay(f, 'It did not go through' + (res.j && typeof res.j.message === 'string' ? ' (' + cText(res.j.message, 120) + ')' : '') + '. Please try again in a moment.');
      }, function () { contactSay(f, 'It could not be sent: check the connection and try again.'); })
      .then(function () { contactState.busy = false; f.send.disabled = false; });
  };

  const licencesCard = function licencesCard() {
    var ul = h('ul', { class: 'lic-list' });
    LICENCES.forEach(function (d) {
      var li = h('li', null, d.url ? h('a', { href: d.url }, h('b', { text: d.name })) : h('b', { text: d.name }), ': ' + d.use);
      if (d.lic) li.appendChild(h('span', { class: 'lic-tag' }, d.licUrl ? h('a', { href: d.licUrl, text: d.lic }) : d.lic));
      if (d.cite) {
        var cs = h('span', { class: 'lic-cite' });
        d.cite.forEach(function (c, i) { if (i) cs.appendChild(document.createTextNode('; ')); cs.appendChild(h('a', { href: 'https://doi.org/' + c[1], text: c[0] })); });
        li.appendChild(cs);
      }
      ul.appendChild(li);
    });
    return h('section', { class: 'card lic-card' },
      cardHead('Data and licences', 'Where everything in this app comes from. None of these sources endorses the project.'),
      ul,
      h('p', { class: 'note' }, 'We download, filter and match these data and compute features from them; the models, predictions and scores are our own. The drawings and animations in this app are ours too, and research results are summarized in our own words with a link to each paper.'),
      h('p', { class: 'note' }, 'The project’s code is under the ', h('a', { href: REPO_URL + '/blob/main/LICENSE', text: 'MIT licence' }),
        ', and our results, that is the models’ predictions, scores and specs and the curated text, are under ', h('a', { href: REPO_URL + '/blob/main/LICENSE-results.md', text: 'CC BY 4.0' }),
        '; please cite the repository if you use them.'),
      h('p', { class: 'note' }, 'The desktop app is built with ', h('a', { href: 'https://tauri.app/', text: 'Tauri' }),
        ' and other open-source libraries under MIT, Apache-2.0, MPL-2.0 and similar licences. Their notices ship with the app and are also in ',
        h('a', { href: REPO_URL + '/releases/latest/download/THIRD-PARTY-NOTICES.txt', text: 'THIRD-PARTY-NOTICES.txt' }), '.'));
  };
