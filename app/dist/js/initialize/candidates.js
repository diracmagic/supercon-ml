'use strict';
// candidates: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconCandidates = function initializeSuperconCandidates() {


  /* ---------- Candidate superconductors found by our AI models: the Candidates view ----------
     Each screening round writes a "screen" block into progress.json, with two lists: the conventional candidates that
     Storm ranks ("candidates": its DFT Tc with a 90% range) and, from round 2, the unconventional ones that Hurricane
     ranks ("hurricane.candidates": the chance that each superconducts and its measured Tc if it does, with a 90% range).
     The display sorts each selected group by predicted Tc, highest first; Hurricane uses conditional Tc. Unknown Tc
     stays visible at the end. Published screening scores, group membership and fold ranges are unchanged. Literature
     associations do not establish exact identity or chronology. Only a reviewed earlier experimental positive with
     all identity/condition matches and a sourced frozen prediction moves to the visible reported archive. Limited
     negatives and unresolved outcomes remain alongside predictions, with source and sample conditions. */
  CAND_SHOWN = 10;

  CAND_KINDS = ['storm', 'hurricane'];

  CAND_TRACKS = [
    ['storm_in_domain', 'In training domain', 'Prioritise candidates near Storm’s training data.'],
    ['storm_exploration', 'Exploration', 'Outside or not established to be inside Storm’s training data: these predictions need extra checks.'],
    ['borides', 'Borides', 'Boron-containing candidates; includes predictions inside and outside the training domain.'],
    ['carbides', 'Carbides', 'Carbon-containing candidates; includes predictions inside and outside the training domain.']
  ];

  candidateData = window.SuperconCandidates;

  candState = { all: false, archive: false, sel: { storm: '', hurricane: '' }, key: '', kind: store.get('cand-kind') === 'hurricane' ? 'hurricane' : 'storm',
    track: candidateData.tracks.indexOf(store.get('cand-track')) >= 0 ? store.get('cand-track') : 'storm_in_domain', notesOpen: false };

  CHECK_LABEL = { dft: 'DFT check', experiment: 'Measured' };

  SUB_DIGITS = '₀₁₂₃₄₅₆₇₈₉';

  // what a Hurricane candidate's elements have in common with a known family (screen.py family_guess)
  CAND_FAMILY = { cuprate: 'copper and oxygen, as the cuprates do', 'iron-based': 'iron or nickel with a pnictogen or chalcogen, as the iron-based superconductors do',
    'heavy-fermion': 'an f-electron element, as the heavy-fermion superconductors do', 'other oxide': 'oxygen, as the other unconventional oxides do' };

  // Hurricane's structure types (hurricane2.TYPE_RATIONALE), read from the stoichiometry alone
  CAND_TYPE = { '123_cuprate': '123 cuprates (YBCO)', '214_cuprate': '214 cuprates', electron_doped_cuprate: 'electron-doped cuprates',
    Bi_cuprate: 'Bi-based cuprates', Tl_cuprate: 'Tl-based cuprates', Hg_cuprate: 'Hg-based cuprates', infinite_layer_cuprate: 'infinite-layer cuprates',
    '1111_pnictide': '1111 iron pnictides', '122_pnictide': '122 iron pnictides', '111_pnictide': '111 iron pnictides', '11_chalcogenide': '11 iron chalcogenides',
    '122_chalcogenide': '122 iron chalcogenides', nickel_pnictide: 'nickel pnictides', '115_heavy_fermion': '115 heavy-fermion compounds',
    '122_heavy_fermion': '122 heavy-fermion compounds', nickelate_oxide: 'nickelates', bismuthate_oxide: 'bismuthates', ruthenate_oxide: 'ruthenates',
    cobaltate_oxide: 'cobaltates' };


  /* ---------- elements: symbols and covalent radii (pm; B. Cordero et al., Dalton Trans. 2832 (2008)) ---------- */
  XT_EL = ('H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr ' +
    'Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg ' +
    'Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm').split(' ');

  XT_R = [31, 28, 128, 96, 84, 76, 71, 66, 57, 58, 166, 141, 121, 111, 107, 105, 102, 106, 203, 176, 170, 160, 153, 139,
    139, 132, 126, 124, 132, 122, 122, 120, 119, 120, 120, 116, 220, 195, 190, 175, 164, 154, 147, 146, 142, 139, 145, 144,
    142, 139, 139, 138, 139, 140, 244, 215, 207, 204, 203, 201, 199, 198, 198, 196, 194, 192, 192, 189, 190, 187, 187, 175,
    170, 162, 151, 144, 141, 136, 136, 132, 145, 146, 148, 140, 150, 150, 260, 221, 215, 206, 200, 196, 190, 187, 180, 169];

  XT_Z = {};

  XT_EL.forEach(function (s, i) { XT_Z[s] = i; });

  /* The McMillan limit: about 40 K, long thought to be the ceiling for conventional superconductors after McMillan's
     1968 analysis. Two highlights, and nothing else is highlighted however high its prediction:
     - "worth an experiment": our prediction is above the limit and passes every test we set before suggesting a
       measurement to experimental groups: more likely than not to superconduct, inside its model's training data, made
       before (in ICSD) or, after a full DFT calculation, on the convex hull; a Storm candidate also needs the low end of
       its 90% range, or a full DFT calculation, above the limit. A check below the limit takes it off.
     - "confirmed": a measurement above the limit that is published (its "ref" is in REFS) and that another group has
       reproduced ("confirmed": true, with that report in "ref2"). */
  MCMILLAN_K = 40;
  WORTH_P = 0.5;
  WORTH_HULL = 0.005;

};
