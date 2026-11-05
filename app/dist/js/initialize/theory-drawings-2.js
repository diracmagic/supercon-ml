'use strict';
// theory-drawings: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconTheoryDrawings2 = function initializeSuperconTheoryDrawings2() {

  MINI_ALT = {
    london: 'Magnetic field lines pass straight through a round sample above Tc and bend around it once it is cooled below Tc, while a small plot shows the field decaying exponentially inside the surface over the penetration depth λ.',
    gl: 'A free-energy curve turns from a single well at zero above Tc into a double well below Tc and a ball rolls into the new minimum, while beside it a triangular lattice of vortices appears, each carrying one flux quantum with supercurrent circling it.',
    bcs: 'An electron moving between rows of positive ions pulls them toward its path and leaves a positive wake, a second electron moving the other way falls into the wake and the two bind into a pair of momentum k with spin up and −k with spin down, and the density of states opens an energy gap 2Δ with sharp peaks at its edges.',
    eliashberg: 'The phonon spectrum α²F(ω), with an acoustic and an optical hump, fills in from low to high frequency while the electron–phonon coupling λ climbs to 1.16 and the Allen–Dynes formula with μ* = 0.10 and ω_log ≈ 308 K gives Tc ≈ 26 K.',
    josephson: 'Two superconductors separated by a thin barrier each show a phase arrow; with a voltage applied the phase difference φ winds steadily, the supercurrent I = Ic sin φ oscillates in a scrolling trace, and Cooper pairs shuttle through the barrier with the current.',
    dwave: 'A square Brillouin zone shows the cuprate Fermi surface wrapped in a gap band whose thickness follows cos kx − cos ky, positive (blue) near (0, ±π), negative (orange) near (±π, 0) and zero at nodes on the diagonals, with a pulsing arrow Q = (π, π) linking points of opposite sign.',
    spm: 'In the Brillouin zone of an iron pnictide, hole pockets at the centre carry a positive gap (blue) and electron pockets at the corners a negative gap (orange), and a pulsing spin-fluctuation arrow Q links a hole pocket to an electron pocket.',
    topo: 'A nanowire lies on a superconductor; as the bulk gap opens, its spread-out standing wave gives way to two Majorana modes glowing at the ends, whose probability density decays exponentially into the wire, while a level diagram keeps one state at zero energy inside the gap.',
    moire: 'Two triangular lattices twisted by a small angle form a moiré pattern whose period grows as the twist shrinks toward the magic angle of about 1.1°, where the two central bands in the band plot become flat.',
    magnet: 'A solenoid cut along its axis shows wire cross-sections with current out of the page on top and into the page below, current pulses running turn by turn along the winding, and a uniform magnetic field through the bore, as in MRI and accelerator magnets.',
    mgb2: 'A top view of the boron honeycomb in MgB₂, with magnesium above the hexagon centres, shows the E₂g phonon: the two boron sublattices oscillate in opposite in-plane directions, stretching and squeezing the boron–boron bonds.',
    rebco: 'A REBCO coated-conductor tape seen in cross-section, with substrate, buffer, a thin superconducting REBCO layer and a silver and copper cap, carries current along the REBCO layer while bubbles of boiling liquid nitrogen rise from it at 77 K.',
    hg1223: 'A time plot shows pressure ramping to about 30 GPa and then being released abruptly, while the Tc of Hg-1223 rises from 133 K toward 164 K and then stays near 151 K after the quench, beside a stack of three CuO₂ planes that is squeezed under pressure.',
    iron: 'A square lattice of iron atoms, with arsenic alternately above and below the square centres, carries spin arrows that fluctuate about a stripe antiferromagnetic pattern in which rows of up spins alternate with rows of down spins.',
    hydride: 'A rotating view of a 32-hydrogen local cage around La uses approximate coordinates from a calculated cubic LaH₁₀ structure. Diamond anvils indicate the high-pressure context. The approximately 170 GPa and 250 K labels refer to experiment; this drawing is not a measured atomic trajectory, a pressure fit or a complete unit cell.',
    nickelate: 'An idealised bilayer nickelate fragment has two NiO₂ planes and apical oxygen bridges. Coloured markers illustrate proposed interlayer pairing, not measured electron trajectories or an established mechanism. Inward arrows indicate compressive strain; this is not the structure of infinite-layer nickelates.',
    magic: 'A resistance versus filling trace for magic-angle graphene has a correlated-insulator peak at half filling and superconducting domes on either side where the resistance drops to zero, while a gate marker sweeps across and a label names the state: metal, superconductor or correlated insulator.',
    triplet: 'An electron pair with parallel spins sits on the two lobes of a rotating p-wave orbital whose lobes have opposite signs, giving spin 1 and odd parity, next to a kagome lattice like that of CsV₃Sb₅ in which a 2 × 2 charge-density-wave pattern breathes in and out.',
    heavy: 'Light conduction electrons move among a lattice of large f-electron moments and slow down sharply as screening clouds form around the moments, becoming heavy quasiparticles with an effective mass of about 100 to 1000 electron masses.',
    perovskite: 'An idealised cubic ABO₃ perovskite seen along one axis: corner-sharing BO₆ octahedra with oxygen at the shared corners and the larger A cation in the cavities between them. The octahedra rock back and forth in an alternating tilt, drawn with an exaggerated angle. This is a schematic lattice, not the measured structure or a measured vibration of SrTiO₃, BaPb₁₋ₓBiₓO₃ or Ba₀.₆K₀.₄BiO₃, and it shows no dopant positions.',
    chevrel: 'A Chevrel-phase cluster turns in view: six molybdenum atoms at the corners of an octahedron inside a cube of eight sulphur atoms, with lead ions in the spaces between clusters. The drawing is an idealised Mo₆S₈ unit at an arbitrary viewing angle; it is not measured coordinates, and the very high upper critical field of PbMo₆S₈ is not depicted.',
    organic: 'Flat organic molecules stand in two herringbone stacks with a layer of anions between them, and one electron hops from molecule to molecule along a stack, the conduction path of a molecular metal. The molecules are drawn as plain tilted slabs rather than their real atomic skeletons, and no measured structure, pressure or pairing mechanism is shown.',
    fulleride: 'C₆₀ balls sit in a row with alkali ions in the spaces between them, the arrangement of a doped fulleride. The balls turn, one of them swells and shrinks to suggest a vibration inside the molecule, and an electron hops from ball to ball. The cages are drawn as patterned spheres, not as the 60 carbon positions, and the vibration is schematic rather than a measured mode.',
    graphite: 'Graphite sheets seen edge-on, with calcium atoms in the galleries between them moving up and down across the gap, and an electron running along a sheet; a plan view beside it shows one carbon hexagon with calcium above its centre. The spacing and the motion are schematic, not measured coordinates or a measured phonon of CaC₆.',
    ute2: 'The uranium sublattice of UTe₂ turns in view: the nearest uranium atoms form a two-leg ladder running along the a axis, with legs of about 4.2 Å and rungs of about 3.8 Å, the distances reported for the body-centred orthorhombic Immm structure, and a chain of Te(2) atoms runs along the b axis beside it. Only the viewing angle changes; no distance in the drawing moves. The two marked Te(1) atoms show that a second, inequivalent tellurium site exists and are not at measured coordinates; the eightfold UTe₈ prism around each uranium is not drawn, and nothing here depicts the spin-triplet pairing, which is a candidate rather than an established fact.',
    sro: 'An idealised Sr₂RuO₄ layer stack seen from the side: ruthenium–oxygen planes of corner-sharing octahedra, with apical oxygen above and below each ruthenium and strontium in the layers between the planes. The octahedra are drawn untilted, and a soft band sweeps across to pick out the layering and carries no physical meaning. It is a schematic of the layered perovskite, not measured coordinates or a measured distortion, and it shows nothing about the pairing symmetry.',
    diamond: 'A carbon network with tetrahedral bonds, in which a few sites are replaced by boron. Each boron leaves a hole that hops away through the carbon bonds, which is how heavy boron doping turns diamond into a metal and then a superconductor. The lattice is a flat schematic of a three-dimensional structure; the boron sites and hole paths are illustrative, not measured positions.'
  };

  /* ---------- structure animations for the classic superconductors on the Tc chart ----------
     Each one is a labelled schematic of an idealised structure. None is measured atomic
     coordinates, a measured vibration or evidence for a pairing mechanism. */
  (function () {
    var TAU = Math.PI * 2;
    function md(t, p) { t = t % p; return t < 0 ? t + p : t; }
    function font(c, C, size, weight) { c.font = (weight || '400') + ' ' + size + 'px ' + C.font; }
    function seg(c, x0, y0, x1, y1) { c.beginPath(); c.moveTo(x0, y0); c.lineTo(x1, y1); c.stroke(); }
    function ring(c, x, y, r, stroke, lw, fill) {
      c.beginPath(); c.arc(x, y, r, 0, TAU);
      if (fill) { c.fillStyle = fill; c.fill(); }
      if (stroke) { c.lineWidth = lw || 1; c.strokeStyle = stroke; c.stroke(); }
    }
    function lab(c, C, text, x, y, color, size, anchor) {
      font(c, C, size || 10.5, '600');
      c.textAlign = anchor || 'left'; c.textBaseline = 'middle';
      c.fillStyle = color; c.fillText(text, x, y);
      c.textAlign = 'left'; c.textBaseline = 'alphabetic';
    }
    // Every drawing starts from the same clean state, and a failure cannot leak into the next frame.
    function g2(fn) {
      return function (c, C, W, H, t) {
        c.save();
        c.lineCap = 'round'; c.lineJoin = 'round'; c.setLineDash([]); c.globalAlpha = 1;
        try { fn(c, C, W, H, t || 0); } finally { c.restore(); }
      };
    }

    // Corner-sharing BO6 octahedra in projection, with an alternating tilt of exaggerated amplitude.
    function drawPerovskite(c, C, W, H, t) {
      var b = Math.max(26, Math.min(44, Math.min(W / 4.2, H / 2.9))), th = 0.11 * Math.sin(md(t, 6) * TAU / 3);
      var cols = Math.max(2, Math.floor((W - 24) / b)), rows = Math.max(2, Math.floor((H - 30) / b));
      var ox = (W - (cols - 1) * b) / 2, oy = (H - (rows - 1) * b) / 2 + 4, i, j, k, a, px, py;
      for (j = 0; j < rows; j++) for (i = 0; i < cols; i++) {
        px = ox + i * b; py = oy + j * b; a = ((i + j) % 2 ? -th : th);
        c.strokeStyle = C.axis; c.lineWidth = 1.4;
        c.beginPath();
        for (k = 0; k < 4; k++) {
          var an = a + k * Math.PI / 2, qx = px + Math.cos(an) * b / 2, qy = py + Math.sin(an) * b / 2;
          if (k === 0) c.moveTo(qx, qy); else c.lineTo(qx, qy);
        }
        c.closePath(); c.stroke();
        for (k = 0; k < 4; k++) {
          var bn = a + k * Math.PI / 2;
          ring(c, px + Math.cos(bn) * b / 2, py + Math.sin(bn) * b / 2, 3, null, 0, C.aqua);
        }
        ring(c, px, py, 3.4, null, 0, C.accent);
      }
      for (j = 0; j < rows - 1; j++) for (i = 0; i < cols - 1; i++)
        ring(c, ox + i * b + b / 2, oy + j * b + b / 2, 5.2, C.warm, 1.2, C.surface);
      lab(c, C, 'BO₆ octahedra', 10, 13, C.ink2);
      lab(c, C, 'A site', W - 10, 13, C.warm, 10.5, 'right');
      lab(c, C, 'tilt exaggerated', W - 10, H - 11, C.muted, 9.5, 'right');
    }

    // Mo6 octahedron inside an S8 cube, turned about the vertical axis at a fixed tilt.
    function drawChevrel(c, C, W, H, t) {
      var R = Math.max(26, Math.min(W, H) / 3.1), cx = W / 2, cy = H / 2 + 2;
      var ay = md(t, 24) * 0.42, ax = 0.46, ca = Math.cos(ay), sa = Math.sin(ay), cb = Math.cos(ax), sb = Math.sin(ax);
      function pr(p) {
        var x = p[0] * ca + p[2] * sa, z = p[2] * ca - p[0] * sa, y = p[1] * cb - z * sb;
        var zz = p[1] * sb + z * cb, k = 1 + zz * 0.09;
        return [cx + x * R * k, cy + y * R * k, zz];
      }
      var mo = [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]].map(pr);
      var q = 0.78, su = [];
      for (var i = 0; i < 8; i++) su.push(pr([(i & 1 ? q : -q), (i & 2 ? q : -q), (i & 4 ? q : -q)]));
      c.strokeStyle = C.muted; c.lineWidth = 1;
      for (i = 0; i < 8; i++) for (var j = i + 1; j < 8; j++) {
        var bits = (i ^ j), one = bits === 1 || bits === 2 || bits === 4;
        if (one) seg(c, su[i][0], su[i][1], su[j][0], su[j][1]);
      }
      c.strokeStyle = C.accent; c.lineWidth = 1.5;
      for (i = 0; i < 6; i++) for (j = i + 1; j < 6; j++)
        if (!((i >> 1) === (j >> 1))) seg(c, mo[i][0], mo[i][1], mo[j][0], mo[j][1]);
      su.forEach(function (p) { ring(c, p[0], p[1], 3 + p[2] * 0.7, null, 0, C.aqua); });
      mo.forEach(function (p) { ring(c, p[0], p[1], 3.8 + p[2] * 0.8, C.surface, 1.2, C.accent); });
      [[12, 14], [W - 12, 14], [12, H - 14], [W - 12, H - 14]].forEach(function (p) {
        ring(c, p[0], p[1], 5, C.surface, 1.4, C.warm);
      });
      lab(c, C, 'Mo₆', cx, H - 11, C.accent, 10.5, 'center');
      lab(c, C, 'S₈', cx + R * 0.95, cy - R * 0.95, C.aqua);
      lab(c, C, 'Pb', 22, 14, C.warm);
    }

    // Two herringbone stacks of flat molecules with an anion layer between them.
    function drawOrganic(c, C, W, H, t) {
      var n = 5, dy = Math.max(15, (H - 36) / n), half = Math.max(9, Math.min(15, W / 7));
      var sp = Math.min(W * 0.24, 82), x1 = W / 2 - sp, x2 = W / 2 + sp, y0 = (H - (n - 1) * dy) / 2 + 2, i, k;
      [x1, x2].forEach(function (xc, col) {
        for (i = 0; i < n; i++) {
          var ty = y0 + i * dy, an = (i % 2 ? 0.38 : -0.38) * (col ? -1 : 1);
          c.save(); c.translate(xc, ty); c.rotate(an);
          c.fillStyle = col ? C.surface2 : C.surface2; c.strokeStyle = C.ink2; c.lineWidth = 1.2;
          c.beginPath(); c.rect(-half, -3.4, half * 2, 6.8); c.fill(); c.stroke();
          c.restore();
        }
      });
      c.strokeStyle = C.grid; c.lineWidth = 1;
      for (i = 0; i < n + 1; i++) ring(c, W / 2, y0 - dy / 2 + i * dy, 3.4, C.warm, 1.2, C.surface);
      var p = md(t, n * 0.9) / 0.9, site = Math.floor(p), frac = p - site;
      var ey = y0 + Math.min(n - 1, site) * dy + frac * dy;
      ring(c, x1, Math.min(y0 + (n - 1) * dy, ey), 4.2, C.surface, 1.4, C.accent);
      lab(c, C, 'molecular stacks', 10, H - 11, C.ink2);
      lab(c, C, 'anions', W / 2, 12, C.warm, 10, 'center');
    }

    // C60 balls with alkali ions between them; one ball breathes and an electron hops along the row.
    function drawFulleride(c, C, W, H, t) {
      var n = 3, R = Math.max(14, Math.min(26, Math.min(W / 7, H / 3.4))), cy = H / 2 + 2;
      var gap = (W - 24) / n, spin = md(t, 40) * 0.5, br = 1 + 0.08 * Math.sin(md(t, 6) * TAU / 1.5), i, k;
      for (i = 0; i < n; i++) {
        var cx = 12 + gap * (i + 0.5), rr = R * (i === 1 ? br : 1);
        ring(c, cx, cy, rr, C.ink2, 1.4, C.surface2);
        c.save();
        c.beginPath(); c.arc(cx, cy, rr, 0, TAU); c.clip();
        c.strokeStyle = C.muted; c.lineWidth = 0.9;
        for (k = -2; k <= 2; k++) {
          var off = k * rr * 0.4;
          c.beginPath(); c.ellipse(cx, cy, Math.max(1, Math.abs(rr * Math.cos(spin + k * 0.5))), rr, 0, 0, TAU); c.stroke();
          c.beginPath(); c.moveTo(cx - rr, cy + off); c.lineTo(cx + rr, cy + off); c.stroke();
        }
        c.restore();
      }
      for (i = 0; i <= n; i++) ring(c, 12 + gap * i, cy, 3.6, C.surface, 1.2, C.warm);
      var p = md(t, n * 1.1) / 1.1, site = Math.min(n - 1, Math.floor(p)), frac = p - Math.floor(p);
      var ex = 12 + gap * (site + 0.5) + frac * gap * (site < n - 1 ? 1 : 0);
      ring(c, Math.min(W - 12, ex), cy - R - 7, 4, C.surface, 1.4, C.accent);
      lab(c, C, 'C₆₀', 12, H - 11, C.ink2);
      lab(c, C, 'alkali ions', W - 10, H - 11, C.warm, 10.5, 'right');
    }

    // Graphite sheets seen edge-on with calcium in the galleries, and one hexagon in plan view.
    function drawGraphite(c, C, W, H, t) {
      var right = Math.min(78, W * 0.3), pw = W - right - 20, m = 12;
      var rows = 3, dy = Math.max(18, (H - 32) / (rows - 0.2)), y0 = (H - (rows - 1) * dy) / 2;
      var step = Math.max(9, pw / 12), bob = 3.2 * Math.sin(md(t, 6) * TAU / 1.8), i, j, x, up;
      c.strokeStyle = C.ink2; c.lineWidth = 1.6;
      for (j = 0; j < rows; j++) {
        c.beginPath();
        for (i = 0; i * step <= pw; i++) {
          x = m + i * step; up = i % 2 ? 4 : -4;
          if (!i) c.moveTo(x, y0 + j * dy + up); else c.lineTo(x, y0 + j * dy + up);
        }
        c.stroke();
      }
      for (j = 0; j < rows - 1; j++) for (i = 1; i * step < pw; i += 2)
        ring(c, m + i * step, y0 + j * dy + dy / 2 + (j % 2 ? -bob : bob), 4.2, C.surface, 1.3, C.warm);
      var p = md(t, 4) / 4, ex = m + p * pw;
      ring(c, ex, y0 + dy + (Math.floor(p * 12) % 2 ? 4 : -4), 3.8, C.surface, 1.3, C.accent);
      var hx = W - right / 2 - 8, hy = H / 2, hr = Math.min(24, right / 2.4);
      c.strokeStyle = C.axis; c.lineWidth = 1.4;
      c.beginPath();
      for (i = 0; i < 6; i++) {
        var an = i * TAU / 6 + 0.26;
        if (!i) c.moveTo(hx + Math.cos(an) * hr, hy + Math.sin(an) * hr);
        else c.lineTo(hx + Math.cos(an) * hr, hy + Math.sin(an) * hr);
      }
      c.closePath(); c.stroke();
      for (i = 0; i < 6; i++) {
        var cn = i * TAU / 6 + 0.26;
        ring(c, hx + Math.cos(cn) * hr, hy + Math.sin(cn) * hr, 2.8, null, 0, C.ink2);
      }
      ring(c, hx, hy, 4.2, C.surface, 1.3, C.warm);
      lab(c, C, 'Ca between sheets', m, H - 10, C.warm, 10);
      lab(c, C, 'plan view', hx, hy - hr - 10, C.muted, 9.5, 'center');
    }

    // Tetrahedral carbon bonds with substitutional boron; each boron releases a hole that hops away.
    function drawDiamond(c, C, W, H, t) {
      var step = Math.max(20, Math.min(34, W / 6.5)), rows = Math.max(3, Math.floor((H - 26) / (step * 0.72)));
      var cols = Math.max(4, Math.floor((W - 24) / step)), ox = (W - (cols - 1) * step) / 2, oy = (H - (rows - 1) * step * 0.72) / 2;
      var pts = [], i, j;
      for (j = 0; j < rows; j++) for (i = 0; i < cols; i++)
        pts.push({ x: ox + i * step + (j % 2 ? step / 2 : 0), y: oy + j * step * 0.72, i: i, j: j });
      c.strokeStyle = C.axis; c.lineWidth = 1.3;
      pts.forEach(function (p) {
        pts.forEach(function (q) {
          if (q.j !== p.j + 1) return;
          if (Math.abs(q.x - p.x) > step * 0.62) return;
          seg(c, p.x, p.y, q.x, q.y);
        });
      });
      var boron = pts.filter(function (p) { return (p.i * 3 + p.j * 5) % 7 === 2; });
      pts.forEach(function (p) {
        var isB = boron.indexOf(p) >= 0;
        ring(c, p.x, p.y, isB ? 4.4 : 3, C.surface, 1.2, isB ? C.warm : C.ink2);
      });
      var ph = md(t, 5) / 5;
      boron.slice(0, 3).forEach(function (p, k) {
        var a = (ph + k * 0.33) * TAU, r = step * 0.46 * (0.6 + 0.4 * Math.sin(a));
        ring(c, p.x + Math.cos(a) * r, p.y + Math.sin(a) * r * 0.72, 3.4, C.accent, 1.6, C.surface);
      });
      lab(c, C, 'carbon', 10, H - 11, C.ink2);
      lab(c, C, 'boron, with its hole', W - 10, H - 11, C.warm, 10.5, 'right');
    }

    // The UTe2 uranium sublattice, at the U-U distances Honda et al. (arXiv:2211.02361) and the
    // Lewin et al. review (arXiv:2402.06850) report: a two-leg ladder along a, legs 4.16 A, rungs 3.78 A.
    // Only the viewing angle turns; no distance changes. Te(1) is indicative, not measured coordinates.
    function drawUTe2(c, C, W, H, t) {
      var LEG = 4.16, RUNG = 3.78, BSTEP = 6.13;
      var ay = md(t, 36) * 0.34, ax = 0.88, ca = Math.cos(ay), sa = Math.sin(ay), cb = Math.cos(ax), sb = Math.sin(ax);
      function pr(p) {
        var x = p[0] * ca + p[2] * sa, z = p[2] * ca - p[0] * sa;
        return [x, p[1] * cb - z * sb, p[1] * sb + z * cb];
      }
      var uM = [], i, k;
      for (i = 0; i < 5; i++) for (k = 0; k < 2; k++) uM.push([(i - 2) * LEG, 0, (k ? 0.5 : -0.5) * RUNG]);
      var te2M = [-1, 0, 1].map(function (j2) { return [0.5 * LEG, j2 * BSTEP, 0]; });
      var te1M = [[-1.5 * LEG, 0.52 * BSTEP, 0.5 * RUNG], [1.5 * LEG, -0.52 * BSTEP, -0.5 * RUNG]];
      var all = uM.concat(te2M, te1M).map(pr);
      var xs = all.map(function (p) { return p[0]; }), ys = all.map(function (p) { return p[1]; });
      var x0 = Math.min.apply(null, xs), x1 = Math.max.apply(null, xs);
      var y0 = Math.min.apply(null, ys), y1 = Math.max.apply(null, ys);
      var padX = 16, padT = 24, padB = 26;
      var R = Math.min((W - 2 * padX) / Math.max(0.1, x1 - x0), (H - padT - padB) / Math.max(0.1, y1 - y0));
      var ox = (W - (x1 + x0) * R) / 2, oy = (padT + (H - padB) - (y1 + y0) * R) / 2;
      function at(p) { var q = pr(p); return [ox + q[0] * R, oy + q[1] * R, q[2]]; }
      var u = uM.map(function (p, n) { return { p: at(p), i: Math.floor(n / 2), k: n % 2 }; });
      c.strokeStyle = C.accent; c.lineWidth = 2.2;
      for (i = 0; i < u.length; i++) for (k = i + 1; k < u.length; k++) {
        var A = u[i], B = u[k];
        if ((A.k === B.k && Math.abs(A.i - B.i) === 1) || (A.i === B.i && A.k !== B.k))
          seg(c, A.p[0], A.p[1], B.p[0], B.p[1]);
      }
      var te2 = te2M.map(at);
      c.strokeStyle = C.aqua; c.lineWidth = 1.6;
      seg(c, te2[0][0], te2[0][1], te2[2][0], te2[2][1]);
      te2.forEach(function (p) { ring(c, p[0], p[1], 4, C.surface, 1.3, C.aqua); });
      te1M.map(at).forEach(function (p) { ring(c, p[0], p[1], 3.6, C.warm, 1.6, C.surface); });
      u.forEach(function (a) { ring(c, a.p[0], a.p[1], 5, C.surface, 1.4, C.accent); });
      lab(c, C, 'U two-leg ladder along a', 10, 13, C.accent);
      lab(c, C, 'Te(2) chain along b', W - 10, 13, C.aqua, 10.5, 'right');
      lab(c, C, 'legs 4.2 Å · rungs 3.8 Å', 10, H - 11, C.muted, 9.5);
      lab(c, C, 'view angle only', W - 10, H - 11, C.muted, 9.5, 'right');
    }

    // Sr2RuO4 as the layered K2NiF4 perovskite: RuO2 planes of corner-sharing octahedra,
    // apical oxygen above and below each Ru, strontium in the layers between. Drawn untilted.
    function drawSro(c, C, W, H, t) {
      var m = 12, n = Math.max(3, Math.floor((W - 2 * m) / 46)), b = (W - 2 * m) / n;
      var planes = [H * 0.29, H * 0.75], i, j, px;
      planes.forEach(function (py) {
        for (i = 0; i < n; i++) {
          px = m + b * (i + 0.5);
          c.strokeStyle = C.axis; c.lineWidth = 1.4;
          c.beginPath();
          c.moveTo(px - b / 2, py); c.lineTo(px, py - b * 0.36);
          c.lineTo(px + b / 2, py); c.lineTo(px, py + b * 0.36);
          c.closePath(); c.stroke();
          ring(c, px, py - b * 0.36, 3, null, 0, C.aqua);
          ring(c, px, py + b * 0.36, 3, null, 0, C.aqua);
          ring(c, px - b / 2, py, 3, null, 0, C.aqua);
          ring(c, px, py, 3.6, null, 0, C.accent);
        }
        ring(c, m + b * n, py, 3, null, 0, C.aqua);
      });
      var mid = (planes[0] + planes[1]) / 2;
      for (i = 0; i < n; i++) {
        px = m + b * (i + 0.5);
        ring(c, px, mid - b * 0.21, 4.4, C.surface, 1.3, C.warm);
        ring(c, px, mid + b * 0.21, 4.4, C.surface, 1.3, C.warm);
      }
      // A soft band picks out the layering; it carries no physical meaning.
      var sweep = md(t, 7) / 7, bx = m + sweep * (W - 2 * m);
      c.save();
      c.globalAlpha = 0.16; c.fillStyle = C.accent;
      c.fillRect(Math.max(m, bx - 26), planes[0] - b * 0.5, Math.min(52, W - m - bx + 26), planes[1] - planes[0] + b);
      c.restore();
      lab(c, C, 'RuO₂ planes', 10, 13, C.accent);
      lab(c, C, 'Sr between the planes', W - 10, H - 11, C.warm, 10.5, 'right');
      lab(c, C, 'no tilt, idealised', 10, H - 11, C.muted, 9.5);
    }

    MINI_DRAW.perovskite = g2(drawPerovskite);
    MINI_DRAW.chevrel = g2(drawChevrel);
    MINI_DRAW.organic = g2(drawOrganic);
    MINI_DRAW.fulleride = g2(drawFulleride);
    MINI_DRAW.graphite = g2(drawGraphite);
    MINI_DRAW.diamond = g2(drawDiamond);
    MINI_DRAW.ute2 = g2(drawUTe2);
    MINI_DRAW.sro = g2(drawSro);
    MINI_STATIC.perovskite = 0.75;
    MINI_STATIC.chevrel = 3.2;
    MINI_STATIC.organic = 1.8;
    MINI_STATIC.fulleride = 1.1;
    MINI_STATIC.graphite = 1.4;
    MINI_STATIC.diamond = 1.6;
    MINI_STATIC.ute2 = 4.4;
    MINI_STATIC.sro = 2.1;
  })();

};
