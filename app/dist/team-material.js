(function () {
  'use strict';
  const SVG = 'http://www.w3.org/2000/svg';
  const DESCRIPTIONS = Object.freeze({
    hydride_cage: ['Sodalite hydrogen-cage motif', 'A 24-vertex truncated octahedron illustrates the H₂₄ sodalite cage used in some hydride structures. It is not a generic shape for all hydrides. The central metal and idealised cage are a motif, not a complete unit cell.'],
    octahedral_hydride: ['Six-hydrogen coordination motif', 'Six hydrogen sites surround a central atom at the vertices of an octahedron. This illustrates a local XH₆ coordination unit; the remaining atoms, distortions and crystal packing are omitted.'],
    cuprate_layers: ['Copper–oxygen plane fragment', 'Copper sites occupy a square net with oxygen halfway along each in-plane link. One CuO₂-plane fragment is shown; it does not assert the compound’s layer count, lattice constants or pairing mechanism.'],
    nickelate_layers: ['Bilayer nickel–oxygen fragment', 'Two square NiO₂-plane fragments share intermediate apical oxygen sites along Ni–O–Ni links. Other atoms and outer apical sites are omitted. This bilayer motif does not represent infinite-layer nickelates or establish a pairing mechanism.'],
    kagome_net: ['Kagome-plane fragment', 'A planar network of corner-sharing triangles and hexagonal holes illustrates a kagome sublattice. Only this sublattice is shown; no charge-density wave, magnetic order or superconducting mechanism is implied.'],
    boron_carbon_network: ['Honeycomb-plane fragment', 'A hexagonal ring and its outward links illustrate a honeycomb sublattice only when that motif is reported. Colours do not identify elemental occupancy. A boride or carbide formula alone does not imply a honeycomb structure.'],
    intermetallic: ['Body-centred-cubic motif', 'Corner sites and one body-centre site illustrate BCC site geometry. Occupancies, disorder and secondary phases must be read from the source; this diagram is not evidence that a generated target crystal formed.'],
    methodology: ['Materials-search overview', 'Candidate descriptions connect to model evaluation and further checks. This diagram represents a research method, not a verified crystal or an experimental discovery.'],
    unknown: ['Research overview', 'No material-specific structural illustration is assigned to this entry. The diagram shows a generic path from candidate descriptions to evaluation and checks.']
  });
  const kinds = Object.freeze(Object.keys(DESCRIPTIONS).filter(key => key !== 'unknown'));
  const normalizeKind = value => typeof value === 'string' && Object.hasOwn(DESCRIPTIONS, value) ? value : 'unknown';
  // Explicit kinds are assigned only after source review. Broad material-family
  // words alone cannot establish a coordination geometry or crystal structure.
  function classifyMaterial(entry) {
    if (!entry || typeof entry !== 'object' || Array.isArray(entry)) return 'methodology';
    if (kinds.includes(entry.material_visual)) return entry.material_visual;
    const text = ['heading', 'title', 'headline', 'result'].map(key => typeof entry[key] === 'string' ? entry[key].slice(0, 3000) : '').join(' ').toLowerCase().normalize('NFKC');
    // Comparison papers may discuss several unrelated motifs. Use their workflow.
    const families = [ /\bhydrides?\b|\bhydrogen[-– ](?:rich|containing)\b/, /\bcuprates?\b|\bcopper[-– ](?:oxides?|oxygen)\b/, /\bnickelates?\b|\bnickel[-– ](?:oxides?|oxygen)\b/, /\bboron\b|\bborides?\b|\bcarbides?\b|\bb[-–]c[-–]n\b/, /\bintermetallics?\b|\bmetallic alloys?\b/ ];
    if (families.filter(pattern => pattern.test(text)).length > 1) return 'methodology';
    // Negated structural descriptions are never converted into a positive drawing.
    if (/\b(?:not|no|without|failed|absent)\b/.test(text)) return 'methodology';
    const motifs = [];
    if (families[0].test(text) && /\bsodalite\b|\bh24\b/.test(text)) motifs.push('hydride_cage');
    if (families[0].test(text) && /\boctahedr(?:al|on|ons|a)\b/.test(text)) motifs.push('octahedral_hydride');
    if (families[1].test(text)) motifs.push('cuprate_layers');
    if (families[2].test(text) && /\bbilayer\b|\bdouble[- ]layer\b/.test(text) && !/\binfinite[- ]layer\b/.test(text)) motifs.push('nickelate_layers');
    if (/\bkagome\b/.test(text)) motifs.push('kagome_net');
    if (families[3].test(text) && /\bhoneycomb\b/.test(text)) motifs.push('boron_carbon_network');
    if (families[4].test(text) && /\bbcc\b|\bbody[- ]cent(?:er|re)d[- ]cubic\b/.test(text)) motifs.push('intermetallic');
    return motifs.length === 1 ? motifs[0] : 'methodology';
  }
  function geometry(kind) {
    const atoms = [], bonds = [];
    const atom = (x, y, z, type = 0, size = 6) => { atoms.push({ x, y, z, type, size }); return atoms.length - 1; };
    const link = (a, b) => bonds.push([a, b]);
    if (kind === 'hydride_cage') {
      atom(0, 0, 0, 1, 11);
      // The 24 permutations of (0, ±1, ±2): truncated octahedron, not a cube.
      for (const xyz of [[0, 1, 2], [0, 2, 1], [1, 0, 2], [2, 0, 1], [1, 2, 0], [2, 1, 0]]) for (const p of [-1, 1]) for (const q of [-1, 1]) {
        let n = 0; const v = xyz.map(value => value * (value ? (++n === 1 ? p : q) : 1) / 1.8); atom(...v, 0, 4.5);
      }
      for (let i = 1; i < atoms.length; i++) for (let j = i + 1; j < atoms.length; j++) if (Math.abs(Math.hypot(atoms[i].x - atoms[j].x, atoms[i].y - atoms[j].y, atoms[i].z - atoms[j].z) - Math.sqrt(2) / 1.8) < 1e-6) link(i, j);
    } else if (kind === 'octahedral_hydride') {
      atom(0, 0, 0, 1, 10);
      for (const v of [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]]) link(0, atom(...v, 0, 5));
    } else if (kind === 'cuprate_layers' || kind === 'nickelate_layers') {
      const bilayer = kind === 'nickelate_layers', layers = [];
      for (let layer = 0; layer < (bilayer ? 2 : 1); layer++) {
        const sites = [], y = bilayer ? (layer ? .6 : -.6) : 0;
        for (let row = 0; row < 3; row++) for (let col = 0; col < 3; col++) sites.push(atom((col - 1) * .9, y, (row - 1) * .9, 1, 7));
        for (let row = 0; row < 3; row++) for (let col = 0; col < 3; col++) {
          const i = row * 3 + col;
          for (const next of [col < 2 ? i + 1 : -1, row < 2 ? i + 3 : -1]) if (next >= 0) {
            const a = atoms[sites[i]], b = atoms[sites[next]], oxygen = atom((a.x + b.x) / 2, y, (a.z + b.z) / 2, 0, 4.5);
            link(sites[i], oxygen); link(oxygen, sites[next]);
          }
        }
        layers.push(sites);
      }
      if (bilayer) for (let i = 0; i < 9; i++) { const a = atoms[layers[0][i]], oxygen = atom(a.x, 0, a.z, 0, 4.5); link(layers[0][i], oxygen); link(oxygen, layers[1][i]); }
    } else if (kind === 'kagome_net') {
      const spacing = .57;
      for (let i = -1; i <= 1; i++) for (let j = -1; j <= 1; j++) for (const [x, z] of [[0, 0], [1, 0], [.5, Math.sqrt(3) / 2]]) atom(spacing * (2 * i + j + x - .5), 0, spacing * (Math.sqrt(3) * j + z - Math.sqrt(3) / 6), 0, 4.5);
      for (let i = 0; i < atoms.length; i++) for (let j = i + 1; j < atoms.length; j++) if (Math.abs(Math.hypot(atoms[i].x - atoms[j].x, atoms[i].z - atoms[j].z) - spacing) < 1e-6) link(i, j);
    } else if (kind === 'boron_carbon_network') {
      for (let i = 0; i < 6; i++) atom(Math.cos(i * Math.PI / 3), Math.sin(i * Math.PI / 3), 0, 0, 6);
      for (let i = 0; i < 6; i++) { link(i, (i + 1) % 6); const a = atoms[i]; link(i, atom(a.x * 1.6, a.y * 1.6, 0, 0, 4.5)); }
    } else if (kind === 'intermetallic') {
      for (const x of [-.8, .8]) for (const y of [-.8, .8]) for (const z of [-.8, .8]) atom(x, y, z, 0, 6);
      const centre = atom(0, 0, 0, 1, 10);
      for (let i = 0; i < 8; i++) { link(i, centre); for (let j = i + 1; j < 8; j++) if (['x', 'y', 'z'].filter(key => atoms[i][key] !== atoms[j][key]).length === 1) link(i, j); }
    } else {
      atom(-1.35, 0, 0, 0, 12); atom(0, -.65, 0, 1, 12); atom(0, .65, 0, 1, 12); atom(1.35, 0, 0, 0, 12);
      link(0, 1); link(0, 2); link(1, 3); link(2, 3);
    }
    return { atoms, bonds };
  }
  function createMaterialAnimation(options) {
    const doc = options.document, win = options.window, details = options.details;
    const kind = normalizeKind(options.kind), [title, explanation] = DESCRIPTIONS[kind];
    const node = (tag, attrs, text) => { const element = doc.createElement(tag); Object.entries(attrs || {}).forEach(([key, value]) => element.setAttribute(key, value)); if (text) element.textContent = text; return element; };
    const svgNode = (tag, attrs) => { const element = doc.createElementNS(SVG, tag); Object.entries(attrs || {}).forEach(([key, value]) => element.setAttribute(key, value)); return element; };
    const root = node('section', { class: 'team-material', 'aria-label': 'Material illustration' });
    root.appendChild(node('h4', {}, title));
    root.appendChild(node('p', { class: 'team-material-label' }, 'Idealised motif · not a complete crystal or measured motion'));
    const diagram = svgNode('svg', { viewBox: '0 0 320 190', class: 'team-material-diagram', role: 'img', 'aria-label': title + '. Generic illustration; consult the source for the actual material.' });
    root.appendChild(diagram);
    const { atoms, bonds } = geometry(kind), links = bonds.map(() => diagram.appendChild(svgNode('line', { class: 'team-material-bond' })));
    const circles = atoms.map(atom => diagram.appendChild(svgNode('circle', { r: atom.size, class: 'team-material-site team-material-site-' + atom.type })));
    root.appendChild(node('p', { class: 'team-material-explanation' }, explanation));
    if (typeof options.caption === 'string' && options.caption.trim() && options.caption.length <= 800) root.appendChild(node('p', { class: 'team-material-caption' }, options.caption));
    const controls = node('div', { class: 'team-material-controls' });
    const play = node('button', { type: 'button', class: 'btn small', 'aria-label': 'Play material illustration', 'aria-pressed': 'false' }, 'Rotate view');
    const status = node('span', { class: 'team-material-status' }, 'Paused');
    controls.appendChild(play); controls.appendChild(status); root.appendChild(controls);
    const media = typeof win.matchMedia === 'function' ? win.matchMedia('(prefers-reduced-motion: reduce)') : null;
    let reduced = !!media?.matches, visible = !win.IntersectionObserver, playing = false, destroyed = false, frame = null, last = null, elapsed = 0;
    const disposers = [];
    const listen = (target, name, fn) => { if (target?.addEventListener) { target.addEventListener(name, fn); disposers.push(() => target.removeEventListener(name, fn)); } };
    function paint() {
      const method = kind === 'methodology' || kind === 'unknown';
      const angle = method ? 0 : .55 + elapsed / 4200;
      const points = atoms.map(atom => ({ x: 160 + 65 * (atom.x * Math.cos(angle) - atom.z * Math.sin(angle)), y: 93 + 43 * atom.y + 13 * (atom.x * Math.sin(angle) + atom.z * Math.cos(angle)) }));
      bonds.forEach(([a, b], index) => { const line = links[index]; line.setAttribute('x1', points[a].x); line.setAttribute('y1', points[a].y); line.setAttribute('x2', points[b].x); line.setAttribute('y2', points[b].y); });
      circles.forEach((circle, index) => { circle.setAttribute('cx', points[index].x); circle.setAttribute('cy', points[index].y); circle.setAttribute('opacity', method && playing ? String(.55 + .45 * (1 + Math.sin(elapsed / 650 - index)) / 2) : '1'); });
    }
    function updateControl() {
      play.hidden = reduced; play.textContent = playing ? 'Pause illustration' : (kind === 'methodology' || kind === 'unknown' ? 'Play overview' : 'Rotate view');
      play.setAttribute('aria-label', playing ? 'Pause material illustration' : 'Play material illustration');
      play.setAttribute('aria-pressed', String(playing)); status.textContent = reduced ? 'Static view · reduced motion' : playing ? 'Illustration playing' : 'Paused';
    }
    const canPlay = () => !destroyed && !reduced && visible && !doc.hidden && (!details || details.open) && typeof win.requestAnimationFrame === 'function';
    function pause() { playing = false; if (frame !== null) win.cancelAnimationFrame(frame); frame = null; last = null; if (!destroyed) { updateControl(); paint(); } }
    function tick(time) { frame = null; if (!playing || !canPlay()) { pause(); return; } if (last !== null) elapsed += Math.max(0, Math.min(100, time - last)); last = time; paint(); frame = win.requestAnimationFrame(tick); }
    function toggle() { if (playing) { pause(); return; } if (!canPlay()) return; playing = true; last = null; updateControl(); frame = win.requestAnimationFrame(tick); }
    listen(play, 'click', toggle);
    listen(details, 'toggle', () => { if (!details.open) pause(); });
    listen(doc, 'visibilitychange', () => { if (doc.hidden) pause(); });
    listen(media, 'change', () => { reduced = !!media.matches; pause(); });
    const observer = typeof win.IntersectionObserver === 'function' ? new win.IntersectionObserver(entries => { if (destroyed) return; const entry = entries.find(item => item.target === root); if (entry) { visible = entry.isIntersecting && entry.intersectionRatio > 0; if (!visible) pause(); } }, { threshold: 0.01 }) : null;
    if (observer) observer.observe(root);
    paint(); updateControl();
    return Object.freeze({ node: root, pause, destroy() { if (destroyed) return; pause(); destroyed = true; disposers.forEach(dispose => dispose()); observer?.disconnect(); root.textContent = ''; } });
  }
  const api = Object.freeze({ kinds, normalizeKind, classifyMaterial, geometry, createMaterialAnimation });
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else if (typeof window !== 'undefined') window.SuperconMaterialVisual = api;
})();
