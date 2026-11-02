(function () {
  'use strict';
  const SVG = 'http://www.w3.org/2000/svg';
  const DESCRIPTIONS = Object.freeze({
    hydride_cage: ['Hydrogen-rich cage motif', 'A metal centre surrounded by light atoms illustrates a cage motif considered in hydride research. The diagram does not specify a compound, pressure or stable crystal structure.'],
    cuprate_layers: ['Layered copper–oxygen motif', 'Linked square planes illustrate the layered motifs studied in cuprates. Layer count, atomic positions and electronic behaviour must be checked in the cited paper.'],
    nickelate_layers: ['Layered nickel–oxygen motif', 'Two connected planes illustrate a layered nickelate motif. This is a visual guide, not the paper’s crystallographic model or evidence for a pairing mechanism.'],
    boron_carbon_network: ['Light-element network motif', 'A connected light-element network illustrates the structural-design theme. Site colours do not assign a real composition, bonding state or superconducting mechanism.'],
    intermetallic: ['Multicomponent lattice motif', 'Distinct sites illustrate a multicomponent metallic solid. The arrangement is schematic; real phases, disorder and impurity content are established by the study’s measurements.'],
    methodology: ['Materials-search overview', 'Candidate descriptions connect to model evaluation and further checks. This diagram represents a research method, not a verified crystal or an experimental discovery.'],
    unknown: ['Research overview', 'No material-specific structural illustration is assigned to this entry. The diagram shows a generic path from candidate descriptions to evaluation and checks.']
  });
  const kinds = Object.freeze(Object.keys(DESCRIPTIONS).filter(key => key !== 'unknown'));
  const normalizeKind = value => typeof value === 'string' && Object.hasOwn(DESCRIPTIONS, value) ? value : 'unknown';
  // This selects an illustrative theme, never a crystal structure or mechanism.
  // An explicitly assigned, controlled kind takes precedence over keyword hints.
  function classifyMaterial(entry) {
    if (!entry || typeof entry !== 'object' || Array.isArray(entry)) return 'methodology';
    if (kinds.includes(entry.material_visual)) return entry.material_visual;
    const text = ['heading', 'title', 'headline', 'result'].map(key => typeof entry[key] === 'string' ? entry[key].slice(0, 3000) : '').join(' ').toLowerCase();
    const patterns = [
      ['hydride_cage', /\bhydrides?\b|\bhydrogen[-– ](?:rich|containing)\b/],
      ['cuprate_layers', /\bcuprates?\b|\bcopper[-– ](?:oxides?|oxygen)\b/],
      ['nickelate_layers', /\bnickelates?\b|\bnickel[-– ](?:oxides?|oxygen)\b/],
      ['boron_carbon_network', /\bboron\b|\bborides?\b|\bcarbides?\b|\bb[-–]c[-–]n\b/],
      ['intermetallic', /\bintermetallics?\b|\bmetallic alloys?\b/]
    ];
    const matches = patterns.filter(([, pattern]) => pattern.test(text));
    return matches.length === 1 ? matches[0][0] : 'methodology';
  }
  function geometry(kind) {
    const atoms = [], bonds = [];
    const atom = (x, y, z, type = 0, size = 6) => { atoms.push({ x, y, z, type, size }); return atoms.length - 1; };
    const link = (a, b) => bonds.push([a, b]);
    if (kind === 'hydride_cage') {
      atom(0, 0, 0, 1, 11);
      for (const y of [-.72, .72]) for (let i = 0; i < 6; i++) atom(Math.cos(i * Math.PI / 3), y, Math.sin(i * Math.PI / 3), 0, 4.5);
      for (let i = 0; i < 6; i++) { link(1 + i, 1 + (i + 1) % 6); link(7 + i, 7 + (i + 1) % 6); link(1 + i, 7 + i); }
    } else if (kind === 'cuprate_layers' || kind === 'nickelate_layers') {
      for (let layer = 0; layer < 2; layer++) {
        const start = atoms.length;
        for (let row = 0; row < 3; row++) for (let col = 0; col < 3; col++) atom((col - 1) * .8, layer ? .65 : -.65, (row - 1) * .8, (row + col) % 2, (row + col) % 2 ? 4.5 : 7);
        for (let row = 0; row < 3; row++) for (let col = 0; col < 3; col++) { const i = start + row * 3 + col; if (col < 2) link(i, i + 1); if (row < 2) link(i, i + 3); }
      }
      if (kind === 'nickelate_layers') for (const i of [0, 4, 8]) link(i, i + 9);
    } else if (kind === 'boron_carbon_network') {
      for (let i = 0; i < 6; i++) atom(Math.cos(i * Math.PI / 3), Math.sin(i * Math.PI / 3), 0, i % 2, 6);
      for (let i = 0; i < 6; i++) { link(i, (i + 1) % 6); const a = atoms[i]; link(i, atom(a.x * 1.5, a.y * 1.5, .25, (i + 1) % 2, 4.5)); }
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
    root.appendChild(node('p', { class: 'team-material-label' }, 'Schematic illustration · not a measured structure or motion'));
    const diagram = svgNode('svg', { viewBox: '0 0 320 190', class: 'team-material-diagram', role: 'img', 'aria-label': title + '. Generic illustration; consult the source for the actual material.' });
    root.appendChild(diagram);
    const { atoms, bonds } = geometry(kind), links = bonds.map(() => diagram.appendChild(svgNode('line', { class: 'team-material-bond' })));
    const circles = atoms.map(atom => diagram.appendChild(svgNode('circle', { r: atom.size, class: 'team-material-site team-material-site-' + atom.type })));
    root.appendChild(node('p', { class: 'team-material-explanation' }, explanation));
    if (typeof options.caption === 'string' && options.caption.trim() && options.caption.length <= 800) root.appendChild(node('p', { class: 'team-material-caption' }, options.caption));
    const controls = node('div', { class: 'team-material-controls' });
    const play = node('button', { type: 'button', class: 'btn small', 'aria-label': 'Play material illustration', 'aria-pressed': 'false' }, 'Play illustration');
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
      play.hidden = reduced; play.textContent = playing ? 'Pause illustration' : 'Play illustration';
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
  const api = Object.freeze({ kinds, normalizeKind, classifyMaterial, createMaterialAnimation });
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else if (typeof window !== 'undefined') window.SuperconMaterialVisual = api;
})();
