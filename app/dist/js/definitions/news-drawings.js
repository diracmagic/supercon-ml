'use strict';
// news-drawings: shared lexical function definitions; no startup side effects.

  const newsArt = function newsArt(n) {
    var tp = list(n.topics), head = String(n.title || ''), body = head + ' ' + String(n.summary || '') + ' ' + String(n.abstract || '');
    // Match the stated subject before broad tags. These are labelled subject schematics,
    // never reconstructed structures, measured traces or evidence of superconductivity.
    if (/\bStorm\b/i.test(head) && /range|interval|conformal/i.test(head)) return 'news-interval';
    if (/\bRadar\b/i.test(head)) return 'news-routing';
    if (/\bHurricane\b/i.test(head)) return /two.parts|two.stage|[2-9]\.0/i.test(head) ? 'news-two-stage' : 'news-tree';
    if (/\bStorm\b/i.test(head) && !/graph|network/i.test(head)) return 'news-tree';
    if (/literature|retrieval[- ]augmented|question answering|text mining|language model|corpus|structured extraction/i.test(head)) return 'news-literature';
    if (/stripes?|Hubbard|Kondo[- ]Heisenberg/i.test(head)) return 'news-stripes';
    if (/geometry of materials|common features|representation|tangent kernel/i.test(head)) return 'news-features';
    if (/density of states|spectroscop|Raman|muon stopping|ultrasound/i.test(head)) return 'news-spectrum';
    if (/vorti(?:ces|ex)/i.test(head)) return 'news-vortex';
    if (/graphene/i.test(head) && !/twist|moir[eé]/i.test(head)) return /(?:six|6)[- ]layer/i.test(head) ? 'news-layered-six' : 'news-layered';
    if (/electron[– -]phonon|phonon|breathing mode/i.test(head)) return 'news-eph';
    if (/magnon|spin wave/i.test(head) && !/circuit|qubit/i.test(head)) return 'news-stripes';
    if (/graph neural|line[- ]graph|ALIGNN|crystal[- ]graph/i.test(head)) return 'news-graph';
    if (/generat|diffusion|inverse design|structure search|physics judge/i.test(head)) return 'news-search';
    if (/terahertz|picosecond|laser|light pulse/i.test(head)) return 'news-light';
    if (/pressure|diamond anvil|\bGPa\b/i.test(head)) return 'news-pressure';
    if (/nanowire/i.test(head)) return 'news-topo';
    if (/kagome/i.test(head)) return 'news-kagome';
    if (n.ai_kind === 'experiment') return 'news-measurement';
    if (n.ai_kind === 'generation') return 'news-search';
    if (n.ai_kind === 'data' || n.ai_kind === 'review') return 'news-literature';
    var materialTopics = ['Hydrides', 'Cuprates', 'Nickelates', 'Iron-based', 'Moiré and 2D', 'Kagome', 'Heavy fermions'];
    if (materialTopics.filter(function (topic) { return tp.indexOf(topic) >= 0; }).length > 1) return 'news-features';
    if (tp.indexOf('Cuprates') >= 0) return 'news-cuprate';
    if (tp.indexOf('Nickelates') >= 0 && /\bbilayer\b|\bdouble[- ]layer\b/i.test(body) && !/\binfinite[- ]layer\b/i.test(body)) return 'news-nickelate';
    if (tp.indexOf('Nickelates') >= 0) return 'news-layered';
    if (tp.indexOf('Kagome') >= 0) return 'news-kagome';
    if (tp.indexOf('Moiré and 2D') >= 0 && /\btwist(?:ed|ing)?\b/i.test(body)) return 'news-moire';
    if (tp.indexOf('Moiré and 2D') >= 0) return 'news-layered';
    if (tp.indexOf('Iron-based') >= 0) return 'news-iron';
    if (tp.indexOf('Hydrides') >= 0) return 'news-hydride';
    if (tp.indexOf('Heavy fermions') >= 0) return 'news-heavy';
    if (tp.indexOf('Triplet and ruthenates') >= 0 && /triplet/i.test(body)) return 'news-triplet';
    if (tp.indexOf('Topological') >= 0) return 'news-topo';
    if (tp.indexOf('Electron–phonon') >= 0) return 'news-eph';
    if (tp.indexOf('Vortices and junctions') >= 0 && /junction/i.test(body)) return 'news-junction';
    if (tp.indexOf('AI and data') >= 0) return 'news-ai';
    // older feed entries carry "Quantum devices" for any story that mentions quantum computers, so look for a device word too
    if (/qubit|transmon|fluxonium|quantum (processor|computer|computing|information|memory|technolog)|superconducting circuit|circuit QED|single-photon/i.test(head) ||
        /qubit|transmon|fluxonium|circuit QED/i.test(body)) return 'news-qubit';
    if (/meissner|levitat/i.test(head)) return 'news-general';
    if (/experiment|measur|resistance|critical.current|magnet|two (?:quantum |superconducting )states|two flavors/i.test(head)) return 'news-measurement';
    return 'news-research';
  };
