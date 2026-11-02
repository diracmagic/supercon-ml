'use strict';
// theory-view: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconTheoryView = function initializeSuperconTheoryView() {


  /* ---------- Theory & materials view ---------- */
  // f: 'conv' = conventional (phonon-driven), 'cuprate', 'other' = other unconventional. p: needs high pressure. pre: preprint.
  TC_DATA = [
    { n: 'Mercury', y: 1911, tc: 4.2, f: 'conv', ref: 'onnes1911', note: 'the first superconductor' },
    { n: 'Niobium', y: 1930, tc: 9.2, f: 'conv', note: 'highest Tc of any element at ambient pressure' },
    { n: 'Nb₃Sn', y: 1954, tc: 18, f: 'conv', ref: 'matthias1954', note: 'A15 compound used in high-field magnets' },
    { n: 'NbTi', y: 1962, tc: 10, f: 'conv', note: 'the wire inside most MRI magnets' },
    { n: 'Nb₃Ge', y: 1973, tc: 22.3, f: 'conv', ref: 'gavaler1973', note: 'record for 13 years' },
    { n: 'CeCu₂Si₂', y: 1979, tc: 0.6, f: 'other', ref: 'steglich1979', note: 'first heavy-fermion superconductor' },
    { n: 'La–Ba–Cu–O', y: 1986, tc: 35, f: 'cuprate', ref: 'bednorz1986', note: 'start of the cuprate era (onset)' },
    { n: 'YBa₂Cu₃O₇', y: 1987, tc: 93, f: 'cuprate', ref: 'wu1987', note: 'first above liquid-nitrogen temperature' },
    { n: 'Bi-2223', y: 1988, tc: 110, f: 'cuprate', ref: 'maeda1988', note: 'first cuprate wires and tapes' },
    { n: 'Tl-2223', y: 1988, tc: 125, f: 'cuprate', ref: 'parkin1988' },
    { n: 'Hg-1223', y: 1993, tc: 133, f: 'cuprate', ref: 'schilling1993', note: 'ambient-pressure record until 2026' },
    { n: 'Hg-1223 under pressure', y: 1994, tc: 164, f: 'cuprate', p: true, ref: 'gao1994', note: 'at about 30 GPa' },
    { n: 'Sr₂RuO₄', y: 1994, tc: 1, f: 'other', ref: 'maeno1994', note: 'layered perovskite without copper' },
    { n: 'MgB₂', y: 2001, tc: 39, f: 'conv', ref: 'nagamatsu2001', note: 'highest conventional Tc at ambient pressure' },
    { n: 'LaFeAsO₁₋ₓFₓ', y: 2008, tc: 26, f: 'other', ref: 'kamihara2008', note: 'start of the iron-based era' },
    { n: 'SmFeAsO₁₋ₓFₓ', y: 2008, tc: 55, f: 'other', ref: 'ren2008', note: 'iron-based bulk record' },
    { n: 'FeSe', y: 2008, tc: 8, f: 'other', ref: 'hsu2008' },
    { n: 'H₃S', y: 2015, tc: 203, f: 'conv', p: true, ref: 'drozdov2015', note: 'at about 155 GPa' },
    { n: 'Magic-angle graphene', y: 2018, tc: 1.7, f: 'other', ref: 'cao2018', note: 'two sheets twisted by about 1.1°' },
    { n: 'LaH₁₀', y: 2019, tc: 250, f: 'conv', p: true, ref: 'drozdov2019', note: 'at about 170 GPa' },
    { n: 'Infinite-layer nickelate', y: 2019, tc: 15, f: 'other', ref: 'li2019', note: 'Nd₀.₈Sr₀.₂NiO₂ films (onset)' },
    { n: 'UTe₂', y: 2019, tc: 1.6, f: 'other', ref: 'ran2019', note: 'spin-triplet candidate' },
    { n: 'CsV₃Sb₅', y: 2020, tc: 2.5, f: 'other', ref: 'ortiz2020', note: 'kagome metal' },
    { n: 'La₃Ni₂O₇', y: 2023, tc: 80, f: 'other', p: true, ref: 'sun2023', note: 'at about 14 GPa' },
    { n: '(La,Pr)₃Ni₂O₇ films', y: 2025, tc: 40, f: 'other', ref: 'zhou2025', note: 'onset at ambient pressure' },
    { n: 'LaSc₂H₂₄', y: 2025, tc: 298, f: 'conv', p: true, pre: true, ref: 'song2025', note: 'onset 271–298 K at 195–266 GPa; preprint, not yet peer reviewed' },
    { n: 'Nickelate films (2026)', y: 2026, tc: 63, f: 'other', ref: 'zhou2026', note: 'onset at ambient pressure; zero resistance up to 37 K' },
    { n: 'Hg-1223, pressure-quenched', y: 2026, tc: 151, f: 'cuprate', ref: 'deng2026', note: 'onset; metastable state kept at ambient pressure' }
  ];

  TC_RECORD = ['Mercury', 'Niobium', 'Nb₃Sn', 'Nb₃Ge', 'La–Ba–Cu–O', 'YBa₂Cu₃O₇', 'Bi-2223', 'Tl-2223', 'Hg-1223'];

  FAMILIES = {
    conv: { label: 'Conventional (phonons)', cls: 'fam-1' },
    cuprate: { label: 'Cuprates', cls: 'fam-2' },
    other: { label: 'Other unconventional', cls: 'fam-3' }
  };

  TC_LABELS = {
    'YBa₂Cu₃O₇': [-8, -10, 'end'], 'Hg-1223': [-8, -10, 'end'], 'MgB₂': [8, -8, 'start'], 'H₃S': [-8, -10, 'end'],
    'LaH₁₀': [-8, -10, 'end'], 'La₃Ni₂O₇': [-8, -10, 'end'], 'LaSc₂H₂₄': [-10, 16, 'end'], 'Hg-1223, pressure-quenched': [-8, -10, 'end'],
    'Nb₃Ge': [-8, -10, 'end']
  };

  TC_LABELS_NARROW = { 'YBa₂Cu₃O₇': 1, 'H₃S': 1, 'LaH₁₀': 1, 'MgB₂': 1 };


  THEORIES = [
    { anim: 'london', name: 'London equations', year: '1935', who: 'Fritz & Heinz London',
      text: 'The first equations for how a superconductor screens a magnetic field. They explain the Meissner effect: the field dies away within a thin surface layer, the penetration depth, typically tens to hundreds of nanometres.',
      refs: ['meissner1933', 'london1935'], demo: 'meissner' },
    { anim: 'gl', name: 'Ginzburg–Landau theory', year: '1950', who: 'Vitaly Ginzburg & Lev Landau',
      text: 'Describes the superconductor with an order parameter ψ, the wave function of the condensate. Two lengths, the coherence length and the penetration depth, separate type I from type II superconductors; in type II, field enters as a lattice of quantized vortices.',
      refs: ['gl1950', 'abrikosov1957'] },
    { anim: 'bcs', name: 'BCS theory', year: '1957', who: 'John Bardeen, Leon Cooper & Robert Schrieffer',
      text: 'The microscopic theory. An attraction carried by lattice vibrations binds electrons into Cooper pairs with opposite momenta and spins, which condense into one coherent quantum state with an energy gap Δ ≈ 1.76 k_B Tc. Nobel Prize 1972.',
      refs: ['cooper1956', 'bcs1957'], demo: 'pairs' },
    { anim: 'eliashberg', name: 'Eliashberg theory and Allen–Dynes', year: '1960–1975', who: 'Gerasim Eliashberg; William McMillan; Philip Allen & Robert Dynes',
      text: 'Extends BCS to strong coupling with the full spectrum of lattice vibrations, α²F(ω). McMillan, and then Allen and Dynes, condensed it into a formula for Tc in terms of λ, ω_log and μ*. This is the physics our models predict.',
      refs: ['eliashberg1960', 'mcmillan1968', 'allendynes1975'], demo: 'allen-dynes' },
    { anim: 'josephson', name: 'Josephson effect', year: '1962', who: 'Brian Josephson',
      text: 'Cooper pairs tunnel through a thin barrier between two superconductors, carrying a current set by the phase difference. It underlies SQUID magnetometers, voltage standards and superconducting qubits. Nobel Prize 1973.',
      refs: ['josephson1962'] },
    { anim: 'dwave', name: 'd-wave pairing and spin fluctuations', year: '1986–', who: 'Cuprate superconductors',
      text: 'In the cuprates the gap changes sign around the Fermi surface (d-wave symmetry), which phonons alone cannot easily produce. Leading proposals put the pairing glue in antiferromagnetic spin fluctuations or in Anderson’s resonating-valence-bond picture; there is still no consensus. The main ideas are compared under Classic mechanisms of high-Tc superconductivity.',
      refs: ['bednorz1986', 'anderson1987', 'tsuei2000', 'scalapino2012'] },
    { anim: 'spm', name: 's± pairing', year: '2008', who: 'Iron-based superconductors',
      text: 'In iron pnictides the gap is thought to take opposite signs on the hole and electron pockets of the Fermi surface, a state favoured by spin fluctuations that connect the pockets.',
      refs: ['kamihara2008', 'mazin2008', 'kuroki2008'] },
    { anim: 'topo', name: 'Topological superconductivity', year: '2001–', who: 'Alexei Kitaev; Liang Fu & Charles Kane',
      text: 'Some superconductors are predicted to host Majorana modes at edges or in vortices: quasiparticles that are their own antiparticles and a candidate building block for fault-tolerant quantum computers. Experimental confirmation is still debated.',
      refs: ['kitaev2001', 'fukane2008'] },
    { anim: 'moire', name: 'Flat bands and moiré superconductivity', year: '2011–', who: 'Twisted bilayer graphene',
      text: 'Twisting two graphene sheets by about 1.1° flattens the electronic bands, so interactions dominate. The result shows correlated insulating states and superconductivity: a tunable playground for strongly correlated pairing. Flat bands also appear without a twist: in rhombohedral (ABC-stacked) multilayer graphene the bands are flat near their edges, and it superconducts too, with no moiré pattern.',
      refs: ['bistritzer2011', 'cao2018'] }
  ];


  // Classic ideas for the cuprates (and other high-Tc superconductors); open: what is still unsettled.
  MECHANISMS = [
    { anim: 'mott', name: 'Mott insulator and the Hubbard model', year: '1963 · 1987', who: 'John Hubbard; Philip W. Anderson',
      text: 'Band theory says undoped cuprates should be metals, yet they insulate: the repulsion U between two electrons on one copper site stops charge from moving, and the spins order antiferromagnetically through superexchange J ≈ 4t²/U. Strictly, the cuprates are charge-transfer insulators, with the gap between oxygen and copper states, but the low-energy physics is similar. Removing electrons melts the order and superconductivity appears. The Hubbard model, hopping t plus on-site U, is the minimal model of all this.',
      open: 'Whether the plain Hubbard model superconducts is debated: large simulations find stripes and d-wave pairing nearly tied in energy, and adding next-nearest-neighbour hopping tips the balance.',
      refs: ['hubbard1963', 'anderson1987', 'lee2006', 'qin2020'] },
    { anim: 'rvb', name: 'Resonating valence bonds (RVB)', year: '1987', who: 'Philip W. Anderson; G. Baskaran, Z. Zou & P. W. Anderson; G. Kotliar & J. Liu',
      text: 'Anderson proposed that neighbouring copper spins pair into singlets, or valence bonds, that resonate among many arrangements like the bonds in benzene, instead of ordering. The singlets are pairs already: once doped holes let them move, they become charged Cooper pairs. Mean-field versions of the idea predicted d-wave pairing and a spin gap above Tc akin to the pseudogap. Anderson had first proposed RVB in 1973 as a new kind of insulator, and the cuprates revived the search for such quantum spin liquids.',
      open: 'Undoped cuprates order antiferromagnetically rather than forming a spin liquid, and how much RVB physics survives near optimal doping is disputed.',
      refs: ['anderson1973', 'anderson1987', 'baskaran1987', 'kotliar1988', 'lee2006'] },
    { anim: 'zr', name: 't–J model and Zhang–Rice singlets', year: '1977 · 1988', who: 'K. A. Chao, J. Spałek & A. M. Oleś; Victor Emery; Fu-Chun Zhang & T. Maurice Rice',
      text: 'In the CuO₂ plane a doped hole sits mostly on the four oxygens around a copper and locks with the copper spin into a singlet, the Zhang–Rice singlet. It moves through the antiferromagnet like a vacancy, which reduces Emery’s three-band model of copper and oxygen orbitals to the one-band t–J model, first derived from the Hubbard model at large U in 1977: hopping t with no double occupancy, plus the exchange J between neighbouring spins.',
      open: 'How much of the cuprates one band can capture, and whether these models reach the observed Tc, is tested with ever larger simulations.',
      refs: ['chao1977', 'emery1987', 'zhangrice1988', 'lee2006'] },
    { anim: 'spinglue', name: 'Spin-fluctuation pairing', year: '1986–', who: 'D. Scalapino, E. Loh & J. Hirsch; K. Miyake, S. Schmitt-Rink & C. Varma; P. Monthoux, A. Balatsky & D. Pines',
      text: 'Near an antiferromagnet, electrons can pair by exchanging spin fluctuations, a magnetic stand-in for phonons. The interaction repels two electrons on the same site but attracts them on neighbouring sites, so the pair spreads onto the neighbours with a plus sign along x and a minus sign along y. That is d-wave symmetry, later confirmed by phase-sensitive experiments.',
      open: 'Strong spin fluctuations are seen with neutrons and X-rays, but whether they alone can account for a Tc near 100 K is still argued.',
      refs: ['scalapino1986', 'miyake1986', 'monthoux1991', 'scalapino2012', 'tsuei2000'] },
    { anim: 'stripes', name: 'Stripes and intertwined orders', year: '1989–1995', who: 'Jan Zaanen & Olle Gunnarsson; John Tranquada and colleagues; Eduardo Fradkin & Steven Kivelson',
      text: 'Doped holes can gather into rivers of charge that separate antiferromagnetic domains, with the spin pattern flipping across each river. Predicted by mean-field theory in 1989 and seen with neutrons in 1995, static stripes are strongest near 1/8 doping, where Tc dips in La₂₋ₓBaₓCuO₄. Charge order has since been found in most cuprate families.',
      open: 'Whether fluctuating stripes help pairing or compete with it, and how they intertwine with a pair-density wave, is still open.',
      refs: ['zaanen1989', 'tranquada1995', 'fradkin2015'] },
    { anim: 'phase', name: 'Phase fluctuations and preformed pairs', year: '1989–1995', who: 'Yasutomo Uemura and colleagues; Victor Emery & Steven Kivelson',
      text: 'In underdoped cuprates the superfluid density is small, so the phase of the pair wave function is floppy. Emery and Kivelson argued that Tc is then set by when the phases line up rather than when pairs form, in line with Uemura’s finding that Tc tracks the superfluid density. Pairs that survive above Tc would explain part of the pseudogap and the large Nernst signal above Tc.',
      open: 'Pairing is seen above Tc only over a limited range; how far it extends, and how it relates to the pseudogap at higher temperatures, is still debated.',
      refs: ['uemura1989', 'emery1995', 'wang2006', 'keimer2015'] },
    { anim: 'bipolaron', name: 'Bipolarons', year: '1981–', who: 'Alexandre Alexandrov & Julius Ranninger; J. Georg Bednorz & K. Alex Müller',
      text: 'With strong electron–lattice coupling, an electron drags a local distortion of the lattice with it, a polaron, and two electrons can share one distortion as a bound pair, a bipolaron. Light enough bipolarons would Bose-condense at high temperature. Bednorz and Müller searched copper oxides with Jahn–Teller polarons in mind. For the cuprates the picture is disputed, but recent simulations show that phonons modulating the electrons’ hopping between sites can make light bipolarons.',
      open: 'Bipolarons are usually heavy, which keeps their condensation temperature low; whether a real material hosts light ones is open.',
      refs: ['alexandrov1981', 'alexandrov1981b', 'bednorz1986', 'zhang2023'] },
    { anim: 'strange', name: 'Strange metal and quantum criticality', year: '1989–', who: 'Chandra Varma and colleagues',
      text: 'Near optimal doping, and over a range around p* on the overdoped side, the cuprates are strange metals: the resistivity stays linear in temperature from just above Tc (down to the lowest temperatures when a magnetic field removes superconductivity) up to hundreds of kelvin, with a scattering rate near the Planckian limit ħ/τ ≈ k_B T. An ordinary metal would bend over to T² at low temperature. The marginal Fermi liquid describes this phenomenologically, and many think a quantum critical point hidden under the superconducting dome organizes both the strange metal and the pairing.',
      open: 'There is no accepted microscopic theory of the strange metal, nor of how it connects to superconductivity.',
      refs: ['varma1989', 'legros2019', 'keimer2015'] }
  ];


  MATERIALS = [
    { anim: 'magnet', name: 'NbTi and Nb₃Sn', tag: 'The workhorses', f: 'conv', tc: 'about 10 K and 18 K',
      text: 'Ductile niobium–titanium wire winds the magnets of nearly every MRI scanner and of the Large Hadron Collider; Nb₃Sn reaches higher fields for fusion and next-generation accelerator magnets.',
      refs: ['matthias1954'] },
    { anim: 'mgb2', name: 'MgB₂', tag: 'Conventional record', f: 'conv', tc: '39 K (2001)',
      text: 'A simple, cheap compound with two superconducting gaps. Its Tc is still the highest for a conventional, phonon-driven superconductor at ambient pressure, and it is made into wires.',
      refs: ['nagamatsu2001'] },
    { anim: 'rebco', name: 'YBCO and REBCO tapes', tag: 'Above liquid nitrogen', f: 'cuprate', tc: '93 K (1987)',
      text: 'The first superconductor above 77 K, so it can be cooled with cheap liquid nitrogen. Coated rare-earth barium copper oxide tapes carry large currents in strong fields and drive compact fusion-magnet designs.',
      refs: ['wu1987'] },
    { anim: 'hg1223', name: 'Hg-1223', tag: 'Ambient-pressure record', f: 'cuprate', tc: '133 K (1993) · 151 K (2026)',
      text: 'Held the ambient-pressure record of 133 K for three decades (164 K under pressure). In 2026 a pressure-quench protocol kept a metastable state with an onset of 151 K after the pressure was released.',
      refs: ['schilling1993', 'gao1994', 'deng2026'] },
    { anim: 'iron', name: 'Iron-based superconductors', tag: 'Second high-Tc family', f: 'other', tc: 'up to 55 K in bulk',
      text: 'Discovered in 2008, these layered iron pnictides and chalcogenides showed that high-Tc superconductivity is not unique to copper oxides, with likely sign-changing s± pairing.',
      refs: ['kamihara2008', 'ren2008', 'hsu2008'] },
    { anim: 'hydride', name: 'Hydrides under pressure', tag: 'Record Tc, megabar pressure', f: 'conv', tc: '203 K (H₃S) · 250 K (LaH₁₀)',
      text: 'Hydrogen-rich compounds squeezed to over a million atmospheres are conventional superconductors at record temperatures. A 2025 preprint reports signs of superconductivity up to 298 K in LaSc₂H₂₄ at 195–266 GPa. The open challenge is to keep it at low pressure. The rotating LaH₁₀ local H₃₂ cage uses approximate calculated coordinates; it is not a measured vibration or a structure shared by all hydrides.',
      refs: ['drozdov2015', 'drozdov2019', 'somayazulu2019', 'song2025', 'liu2017hydride'] },
    { anim: 'nickelate', name: 'Nickelates', tag: 'Newest high-Tc family', f: 'other', tc: '≈ 80 K under pressure · 63 K onset in films',
      text: 'Infinite-layer nickelate films superconducted in 2019, and bilayer La₃Ni₂O₇ reached about 80 K at 14 GPa in 2023. Since 2025, compressively strained films superconduct at ambient pressure, with onsets above 40 K and up to 63 K in 2026. The animation shows an idealised bilayer motif and one proposed interlayer-pairing scenario; the pairing mechanism is not established by those observations.',
      refs: ['li2019', 'sun2023', 'ko2025', 'zhou2025', 'zhou2026', 'lu2024'] },
    { anim: 'magic', name: 'Magic-angle graphene', tag: 'Tunable superconductivity', f: 'other', tc: 'about 1.7 K (2018)',
      text: 'Two graphene sheets twisted by about 1.1° switch between insulating and superconducting states with a gate voltage, offering a clean, tunable test of strongly correlated pairing.',
      refs: ['bistritzer2011', 'cao2018'] },
    { anim: 'triplet', name: 'Spin-triplet candidates', tag: 'Exotic pairing', f: 'other', tc: 'about 1–2 K',
      text: 'Sr₂RuO₄ and UTe₂ are studied for possible spin-triplet pairing and topological states; kagome metals such as CsV₃Sb₅ combine superconductivity with unusual charge order.',
      refs: ['maeno1994', 'ran2019', 'ortiz2020'] },
    { anim: 'heavy', name: 'Heavy fermions', tag: 'First unconventional', f: 'other', tc: 'about 0.6 K (CeCu₂Si₂)',
      text: 'In CeCu₂Si₂ (1979) electrons behave as if hundreds of times heavier than normal and pair without phonons, opening the field of unconventional superconductivity.',
      refs: ['steglich1979'] }
  ];


  learn = { built: false, table: false, fam: 'all' };

};
