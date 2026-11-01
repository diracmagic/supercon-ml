'use strict';
// demo-player: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconDemoPlayer = function initializeSuperconDemoPlayer() {


  /* ---------- physics demos ---------- */
  DEMOS = [
    { id: 'story', label: 'Project tour', story: true, height: 430, narrowHeight: 480 },
    { id: 'storm', label: 'Our AI model: Storm', storm: true, height: 440, narrowHeight: 540,
      refs: ['friedman2001', 'sklearn2011', 'matthias1955', 'allendynes1975', 'nas2017'] },
    { id: 'hurricane', label: 'Our AI model: Hurricane', hurricane: true, height: 450, narrowHeight: 580,
      refs: ['sommer2023', 'jain2013', 'presland1991', 'friedman2001', 'sklearn2011', 'schilling1993', 'deng2026'] },
    { id: 'radar', label: 'Our AI model: Radar', radar: true, height: 440, narrowHeight: 560,
      refs: ['sommer2023', 'jain2013', 'friedman2001', 'sklearn2011', 'steglich1979', 'kamihara2008', 'ortiz2020'] },
    { id: 'model', label: 'Baselines', model: true, height: 440, narrowHeight: 540,
      refs: ['alexandria2024', 'friedman2001', 'sklearn2011', 'mace2022', 'macemp2023', 'allendynes1975'] },
    { id: 'resistance', label: 'Zero resistance', temp: true, height: 360, refs: ['onnes1911', 'bcs1957'],
      caption: 'Above Tc, electrons scatter off vibrating ions, so a current loses energy as heat. Below Tc they bind into Cooper pairs that move together as one coherent quantum state, and the resistance drops to exactly zero.' },
    { id: 'meissner', label: 'Meissner effect', temp: true, height: 340, refs: ['meissner1933', 'london1935'],
      caption: 'Below Tc a superconductor expels magnetic field from its interior. Screening currents in a thin surface layer (⊗ into the page, ⊙ out of it) cancel the field inside. This is why a magnet can levitate above a cooled superconductor.' },
    { id: 'pairs', label: 'Cooper pairs', temp: true, height: 380, refs: ['cooper1956', 'bcs1957'],
      caption: 'A passing electron pulls the positive ions toward it. The heavy ions relax slowly, so a positively charged wake lingers and attracts a second electron: an attraction carried by lattice vibrations (phonons). Its strength is λ and the typical vibration energy is ω_log, the two quantities our models predict. In BCS theory the paired electrons have opposite momenta and spins, and one pair spans many lattice spacings.' },
    { id: 'allen-dynes', label: 'Predict Tc', temp: false, height: 400, narrowHeight: 600, refs: ['eliashberg1960', 'mcmillan1968', 'allendynes1975'], stormRefs: ['friedman2001', 'xie2018', 'allendynes1975', 'vovk2005', 'alexandria2024'], hurRefs: ['sommer2023', 'presland1991', 'friedman2001', 'schilling1993'],
      caption: 'The Allen–Dynes formula estimates Tc from the electron–phonon coupling λ, the logarithmic phonon frequency ω_log and the Coulomb pseudopotential μ*. Stronger coupling and stiffer, higher-frequency lattice vibrations both raise Tc. Drag the sliders, or point at the map to read off Tc. Pick Storm or Hurricane above to see, step by step, how our models predict Tc for real materials.' }
  ];

  RAMP_LIGHT = ['#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#184f95', '#0d366b'];

  TC_MAX = 80;

  view = ['candidates', 'demos', 'learn', 'papers'].indexOf(store.get('view')) >= 0 ? store.get('view') : 'progress';

  demo = {
    id: 'story', t: 1.4, auto: true, clock: 0, raf: 0, last: 0, built: false,
    scene: 0, sceneT: 0, storyPlay: true, modelStage: 0, modelT: 0, modelPlay: true, modelNodes: [],
    stormStage: 0, stormT: 0, stormPlay: true, stormVer: '', stormNodes: [],
    hurStage: 0, hurT: 0, hurPlay: true, hurNodes: [],
    radStage: 0, radT: 0, radPlay: true, radNodes: [],
    predMode: ['storm', 'hurricane'].indexOf(store.get('pred')) >= 0 ? store.get('pred') : 'formula', predT: 0, predPlay: true, predEx: 0,
    modelVariant: ['foundation', 'hurricane', 'radar'].indexOf(store.get('model')) >= 0 ? store.get('model') : 'baseline',
    canvas: null, ctx: null, W: 0, H: 0, dpr: 1,
    electrons: null, ions: null, e1: null, e2: null, sizeKey: '',
    lam: 1.0, wlog: 300, mu: 0.10, heat: null, heatKey: '', hover: null, fieldKey: '', field: null
  };

  (function () {
    var saved = store.get('demo');
    if (DEMOS.some(function (d) { return d.id === saved; })) demo.id = saved;
  })();

};
