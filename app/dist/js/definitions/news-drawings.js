'use strict';
// news-drawings: shared lexical function definitions; no startup side effects.

  const newsArt = function newsArt(n) {
    var tp = list(n.topics), cards = list(n.cards), head = String(n.title || n.h || ''), text = String(n.summary || n.x || '') + ' ' + String(n.abstract || ''), body = head + ' ' + text;
    // Match the stated subject before broad tags. These are labelled subject schematics,
    // never reconstructed structures, measured traces or evidence of superconductivity.
    if (/\bStorm\b/i.test(head) && /range|interval|conformal/i.test(head)) return 'news-interval';
    if (/\bRadar\b/i.test(head)) return 'news-routing';
    if (/\bHurricane\b/i.test(head)) return /two.parts|two.stage|[2-9]\.0/i.test(head) ? 'news-two-stage' : 'news-tree';
    if (/\bStorm\b/i.test(head) && !/graph|network/i.test(head)) return 'news-tree';
    if (/literature|retrieval[- ]augmented|question answering|text mining|language model|corpus|structured extraction/i.test(head)) return 'news-literature';
    if (/holographic/i.test(head)) return 'news-features';
    // A detector or a diode named in the headline outranks the material that hosts it.
    if (/\bdetectors?\b|(?:photon|particle|radiation) detection|\bbolometers?\b|transition[- ]edge sensor|\bSNSPDs?\b|dark matter|\baxions?\b/i.test(head)) return 'news-detector';
    if (/\bdiodes?\b|non-?reciprocal|rectification|magnetochiral/i.test(head)) return 'news-diode';
    if (/weak[- ]links?/i.test(head)) return 'news-junction';
    // Method-specific lattice numerics outrank the model they solve.
    if (/neural[- ]network (?:quantum states?|wave ?functions?)|\bNQS\b/i.test(head)) return 'news-nqs';
    if (/\bcylinders?\b/i.test(head) && /Hubbard|t-J\b|\blegs?\b/i.test(head)) return 'news-cylinder';
    if (/ultracold|cold atoms?|optical lattices?|quantum gas/i.test(head)) return 'news-coldatoms';
    if (/stripes?(?![- ]domain)|Hubbard|Kondo[- ]Heisenberg/i.test(head)) return 'news-stripes';
    if (/geometry of materials|common features|representation|tangent kernel/i.test(head)) return 'news-features';
    // A graph network that also predicts spectra is still a graph network.
    if (/graph neural|line[- ]graph|ALIGNN|crystal[- ]graph|graph networks?/i.test(head)) return 'news-graph';
    if (/density of states|spectroscop|Raman|muon stopping|ultrasound/i.test(head)) return 'news-spectrum';
    // A twisted-light vortex beam is an optical probe, not flux vortices in the sample.
    if (/optical vort|vortex beams?|vortex light/i.test(head)) return 'news-light';
    if (/vort(?:ex|ices)|fluxons?|Abrikosov/i.test(head)) return 'news-vortex';
    if (/quasiparticle interference|\bQPI\b|\bripples?\b/i.test(head)) return 'news-qpi';
    if (/re-?entrant|\brevives?\b|field[- ](?:boosted|stabili[sz]ed|enhanced|induced superconduct)/i.test(head)) return 'news-reentrant';
    if (/domain walls?|heterogene|inhomogene|patchwork|mosaic|\bpuddles?\b|granular/i.test(head)) return 'news-domains';
    if (/\bdisorder|\bdirty\b/i.test(head)) return 'news-disorder';
    if (/graphene/i.test(head)) {
      if (/proximiti/i.test(head)) return 'news-proximity';
      if (/interfaces?/i.test(head)) return 'news-interface';
      var grapheneText = body.replace(/\b(?:without|no|absence of)\s+(?:a\s+)?moir[eé](?:\s+pattern)?\b/gi, '');
      if (/twist|moir[eé]|magic[- ]angle/i.test(grapheneText)) return 'news-moire';
      return /(?:six|6)[- ]layer|hexalayer/i.test(head) ? 'news-layered-six' : 'news-layered';
    }
    if (/electron[– -]phonon|phonon|breathing mode|\bbipolarons?\b|\bpolarons?\b|thermal bosons?/i.test(head) && !/qubit|transmon/i.test(head)) return 'news-eph';
    if (/magnon|spin wave|spin[- ]fluctuat|paramagnon/i.test(head) && !/circuit|qubit/i.test(head)) return 'news-spinfluct';
    if (/\bgenerative\b|\bgenerat(?:e|es|ed|ing)\b|diffusion(?: models?| and| for| transformer)|inverse design|structure search|physics judge/i.test(head)) return 'news-search';
    if (/terahertz|picosecond|femtosecond|laser|light pulse|light[- ]induced|photo-?(?:galvanic|current|induced)|mid-infrared|^light\b|optical(?:ly)? (?:pump|driv)|Floquet/i.test(head)) return 'news-light';
    if (/\b(?:half[- ])?domes?\b|phase diagram/i.test(head)) return 'news-dome';
    var pressureText = head.replace(/\bambient[- ]pressure\b|\b(?:without|no)\s+(?:applied\s+|external\s+)?pressure\b|\bpressure[- ]free\b|\b(?:partial|vapou?r|gas)\s+pressures?\b/gi, '');
    if (/pressur(?:e|i[sz]ed|i[sz]ing)|diamond anvil|\bGPa\b|\bsqueez/i.test(pressureText)) return 'news-pressure';
    if (/\bs\s?±|\bs\+-|s[- ]plus[- ]minus|sign[- ](?:revers|chang)|nodeless/i.test(head)) return 'news-multigap';
    if (/\bd[- ]wave\b/i.test(head)) return 'news-dwave';
    if (/(?:superconducting|leading[- ]edge|spectral) gap\b|pseudogap/i.test(head)) return 'news-gapdos';
    if (/nanowire/i.test(head)) return 'news-topo';
    if (/kagome/i.test(head)) return 'news-kagome';
    if (/Zhang[– -]Rice/i.test(head)) return 'news-zr';
    if (/apical/i.test(head)) return 'news-apical';
    if (/coexist\w*[^.]*antiferromagnet|antiferromagnet\w*[^.]*coexist/i.test(head)) return 'news-competition';
    if (/cuprate|CuO[₂2]/i.test(head)) return 'news-cuprate';
    var bilayerNi = /\bbilayer\b|\bdouble[- ]layer\b|Ni\s?[₂2]\s?O\s?[₇7]/i.test(body) && !/\binfinite[- ]layer\b|monolayer[- ]trilayer/i.test(body);
    if (/nickelate|Ni\s?[₂2]\s?O\s?[₇7]/i.test(head)) return bilayerNi ? 'news-nickelate' : 'news-layered';
    if (n.ai_kind === 'experiment') return 'news-measurement';
    if (n.ai_kind === 'generation') return 'news-search';
    if (n.ai_kind === 'data' || n.ai_kind === 'review') return 'news-literature';
    // Further headline subjects with their own schematic, ahead of broad topic tags.
    // A retraction or null result keeps the neutral icon rather than a material motif.
    if (/retract|withdrawn|debunk|no superconductivity|not superconduct|absence of superconductivity/i.test(head)) return 'news-research';
    if (/Majorana|Kitaev/i.test(head)) return 'news-topo';
    if (/qubit|transmon|fluxonium|quantum (?:processor|computer|computing|information|memory|random[- ]access)|superconducting (?:circuit|processor)|circuit QED|\bQRAM\b/i.test(head)) return 'news-qubit';
    if (/time[- ]reversal|\bTRSB\b|chiral (?:\w+[- ])?superconduct/i.test(head)) return 'news-trsb';
    if (/kekul/i.test(head)) return 'news-kekule';
    if (/FFLO|Fulde|Larkin|Ovchinnikov|pair[- ]density[- ]waves?|\bPDW\b|pair[- ]density modulation|finite[- ]momentum pair|varies with the lattice/i.test(head)) return 'news-fflo';
    if (/Zeeman|spin[- ]imbalanc|Pauli[- ]limit|Ising superconduct/i.test(head)) return 'news-zeeman';
    if (/molecul|triangulene|Shiba|\bYSR\b|adatoms?|magnetic impurit|spin chains?/i.test(head)) return 'news-molecule';
    if (/\bSRF\b|accelerator|cryomodule|radio[- ]frequency|beam acceleration/i.test(head)) return 'news-rf';
    if (/transmission lines?|microwave photons?|\bresonators?\b|kinetic[- ]inductance/i.test(head)) return 'news-resonator';
    if (/cavit(?:y|ies)|vacuum[- ](?:fluctuation|enhanced)|vacuumtronic|Casimir|light[- ]matter|polaritons?|split[- ]ring/i.test(head)) return 'news-cavity';
    if (/\bmagnets?\b|solenoids?|\bcoils?\b|\bMRI\b|\bfusion\b|maglev|superconducting (?:magnetic )?mirror/i.test(head) && !/odd[- ]parity magnet/i.test(head)) return 'news-coil';
    if (/\bcables?\b|\btapes?\b|\bwires?\b|\bkA\b|current leads?|powering|power (?:lines?|links?|transmission)/i.test(head)) return 'news-cable';
    if (/Little[- ]Parks|flux(?:oid)? quantiz|fluxoid|\brings?\b|\bSQUIDs?\b|\bh\/[246]e\b/i.test(head)) return 'news-ring';
    if (/ultracold|cold atoms?|optical lattices?|atomic gas|Fermi gas|Bose[- ]Einstein|tweezers?|atom by atom|quantum gas/i.test(head)) return 'news-coldatoms';
    if (/penetration depth|coherence length|superfluid (?:density|stiffness)|phase stiffness|London (?:length|depth)|accommodate magnetic|field penetration|field screening/i.test(head)) return 'news-penetration';
    if (/multi[- ]?gap|two[- ]gap|multi[- ]?band|two[- ]band|nodeless|Leggett/i.test(head)) return 'news-multigap';
    if (/tunnell?ing (?:spectroscop|measures|gap|conductance)|\bgaps?\b|pseudogap/i.test(head.replace(/\bband[- ]gaps?\b/gi, ''))) return 'news-gapdos';
    if (/Andreev/i.test(head)) return 'news-andreev';
    if (/Josephson|weak[- ]links?|\bjunctions?\b|co-?tunnel|three[- ]terminal|quantum dots?/i.test(head)) return 'news-junction';
    if (/\btwist(?:ed)?\b|twist[- ]angle|moir[eé]|magic[- ]angle/i.test(head)) return 'news-moire';
    if (/charge[- ]density[- ]waves?|\bCDW\b/i.test(head)) return 'news-stripes';
    if (/competi(?:tion|ng)|rivalry|coexist|tetracritic|multi-?component|phase transition between|two (?:superconducting |competing |quantum )?(?:states|orders|phases)|\bnematic\b|intertwined orders?/i.test(head)) return 'news-competition';
    if (/altermagnet|antiferromagnet|ferromagnet|magnetic order|magnetism|exchange[- ]coupled|odd[- ]parity magnets?|N[eé]el/i.test(head)) return 'news-magnetism';
    if (/proximit/i.test(head)) return 'news-proximity';
    if (/thermoelectric|thermal (?:transport|conductivity|Hall)|heat (?:transport|conduction|flow)|Nernst|Seebeck|thermali[sz]ation/i.test(head)) return 'news-thermal';
    if (/\bmonolayer\b(?!s)|atom(?:ically|ic)?[- ]thin|single[- ]layer|one[- ]atom[- ]thick/i.test(head)) return 'news-monolayer';
    if (/interfaces?|thin[- ]films?|\bfilms?\b|heterostructures?|epitax|substrates?|\bgrowth\b|surface superconduct/i.test(head) || /[A-Z][a-z]?(?:[A-Z][a-z]?|\d)+\s?\/\s?[A-Z][a-z]?(?:[A-Z][a-z]?|\d)+/.test(head)) return 'news-interface';
    var materialTopics = ['Hydrides', 'Cuprates', 'Nickelates', 'Iron-based', 'Moiré and 2D', 'Kagome', 'Heavy fermions'];
    if (materialTopics.filter(function (topic) { return tp.indexOf(topic) >= 0; }).length > 1) return 'news-features';
    if (tp.indexOf('Cuprates') >= 0) return 'news-cuprate';
    if (tp.indexOf('Nickelates') >= 0 && bilayerNi) return 'news-nickelate';
    if (tp.indexOf('Nickelates') >= 0) return 'news-layered';
    if (tp.indexOf('Kagome') >= 0) return 'news-kagome';
    if (tp.indexOf('Moiré and 2D') >= 0 && /\btwist(?:ed|ing)?\b/i.test(body)) return 'news-moire';
    if (tp.indexOf('Moiré and 2D') >= 0) return 'news-layered';
    if (tp.indexOf('Iron-based') >= 0) return 'news-iron';
    if (tp.indexOf('Hydrides') >= 0) return 'news-hydride';
    if (tp.indexOf('Heavy fermions') >= 0) return 'news-heavy';
    if (tp.indexOf('Triplet and ruthenates') >= 0 && /triplet/i.test(body)) return 'news-triplet';
    if (tp.indexOf('Topological') >= 0) return 'news-topo';
    // Older feed runs tagged any "unconventional superconductor" electron–phonon; the article's own words decide.
    if (tp.indexOf('Electron–phonon') >= 0 && /electron[- –]phonon|phonon|Eliashberg|McMillan|Allen[- ]Dynes|MgB\s?[₂2]|Nb\s?[₃3]\s?Sn|NbTi|\bconventional superconduct/i.test(body)) return 'news-eph';
    if (tp.indexOf('Vortices and junctions') >= 0 && /junction/i.test(body)) return 'news-junction';
    if (tp.indexOf('AI and data') >= 0) return 'news-ai';
    // older feed entries carry "Quantum devices" for any story that mentions quantum computers, so look for a device word too
    if (/qubit|transmon|fluxonium|quantum (processor|computer|computing|information|memory|technolog)|superconducting circuit|circuit QED|single-photon/i.test(head) ||
        /qubit|transmon|fluxonium|circuit QED/i.test(body)) return 'news-qubit';
    if (/meissner|levitat/i.test(head)) return 'news-general';
    if (/experiment|measur|resistance|critical.current|magnet|shot noise|two (?:quantum |superconducting )states|two flavors/i.test(head)) return 'news-measurement';
    // Curated entries carry Theory & materials cards; only material cards choose a structure.
    if (cards.indexOf('hydride') >= 0) return 'news-hydride';
    if (cards.indexOf('nickelate') >= 0) return bilayerNi ? 'news-nickelate' : 'news-layered';
    if (cards.indexOf('iron') >= 0) return 'news-iron';
    if (cards.indexOf('rebco') >= 0 || cards.indexOf('hg1223') >= 0) return 'news-cuprate';
    if (cards.indexOf('heavy') >= 0) return 'news-heavy';
    if (cards.indexOf('mgb2') >= 0) return 'news-multigap';
    if (cards.indexOf('josephson') >= 0) return 'news-junction';
    if (cards.indexOf('topo') >= 0) return 'news-topo';
    if (cards.indexOf('magnet') >= 0) return 'news-coil';
    // Only an explicit experimental setting in the summary picks a scene when the headline is generic.
    if (/ultracold|cold atoms?|optical lattices?|quantum gas microscope|Fermi gas/i.test(text)) return 'news-coldatoms';
    if (/patchwork|mosaic of|heterogeneous (?:mixture|crystal|structure)/i.test(text)) return 'news-domains';
    if (/\b(?:high|hydrostatic|extreme)[- ]pressure\b|diamond[- ]anvil|\b\d+(?:\.\d+)?\s?GPa\b/i.test(text) && !/ambient[- ]pressure|without (?:applied )?pressure/i.test(text)) return 'news-pressure';
    if (/(?:\b\d+|\bten|\btwenty|\bthirty|\bforty|\bfifty|\bhundred)[- ]years? (?:of|after|later|on)\b|\bafter (?:\w+ )?years\b|anniversary|history of|retrospective|decades? of/i.test(head)) return 'news-timeline';
    return 'news-research';
  };

  // Article descriptions are assembled only from public source text. These are
  // diagrams of what the source discusses, not recovered crystal coordinates,
  // measured traces, proof of a mechanism or an independent literature review.
  const newsArticleDescribe = function newsArticleDescribe(article) {
    var n = article || {}, sub = '₀₁₂₃₄₅₆₇₈₉', fields = [];
    function plain(value) {
      return String(value || '').replace(/<[^>]*>/g, '').replace(/[₀-₉]/g, function (x) { return String(sub.indexOf(x)); })
        .replace(/\\(?:mathrm|text|textrm)\{([^}]+)\}/g, '$1').replace(/[$_{}]/g, '').replace(/\s+/g, ' ').trim();
    }
    [['title', n.title || n.h], ['summary', n.summary], ['abstract', n.abstract], ['curated text', n.x]].forEach(function (entry) {
      var text = plain(entry[1]); if (text) fields.push({ field: entry[0], text: text });
    });
    var title = fields.length ? fields[0].text : 'Research record', all = fields.map(function (f) { return f.text; }).join(' ');
    function evidence(pattern, positiveOnly) {
      for (var i = 0; i < fields.length; i++) {
        var scan=new RegExp(pattern.source,pattern.flags.replace(/g/g,'')+'g'), hit;
        while((hit=scan.exec(fields[i].text))){
          var before=fields[i].text.slice(0,hit.index).split(/[.!?;]/).pop(),after=fields[i].text.slice(hit.index+hit[0].length).split(/[.!?;]/)[0];
          var historical=fields[i].field!=='title' && /\b(?:previous(?:ly)?|earlier|historically|prior studies|past studies|before our)\b/i.test(before.slice(-90)+' '+after.slice(0,50));
          var negated=/\b(?:no|not|without|neither|absence of|lack of)\b[^,;.!?]{0,55}$/i.test(before) || /^[^,;.!?]{0,40}\b(?:not|never)\s+(?:observed|measured|performed|applied|detected|used|present)/i.test(after);
          if(positiveOnly && (historical||negated)) continue;
          return { text: hit[0], field: fields[i].field, excerpt: fields[i].text.slice(Math.max(0, hit.index - 36), hit.index + hit[0].length + 56) };
        }
      }
      return null;
    }
    var facts = [];
    function add(id, label, pattern) {
      var hit = evidence(pattern, true);
      if (hit && id === 'pressure' && /\b(?:without|no)\s+(?:applied |external |high[- ])?pressure\b/i.test(hit.excerpt)) hit = null;
      if (hit) facts.push({ id: id, label: label, text: hit.text, field: hit.field, excerpt: hit.excerpt });
      return hit;
    }
    // Numeric layer counts are explicit in the source; "layered" alone has no
    // inferred layer count. "Infinite-layer" is a phase name, not one sheet.
    var layerMap = { mono: 1, bi: 2, tri: 3, tetra: 4, penta: 5, hexa: 6, hepta: 7, octa: 8, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8 }, layerValues = [], layerEvidence = null;
    for(var lf=0;lf<fields.length;lf++) {
      var layerText=fields[lf].text.replace(/\b(two|three|four|five|six|seven|eight|[1-8])-\s*(?:and|or)\s+(two|three|four|five|six|seven|eight|[1-8])-layer\b/gi,'$1-layer and $2-layer');
      var layerPattern=/\b(?:mono|bi|tri|tetra|penta|hexa|hepta|octa)layer\b|\b(?:mono|bi|tri|four|five|six|seven|eight|two|three|[1-8])[- ]layer\b/gi, found=[],layerMatch;
      while((layerMatch=layerPattern.exec(layerText))){
        var beforeLayer=layerText.slice(0,layerMatch.index).split(/[.!?;]/).pop(),afterLayer=layerText.slice(layerMatch.index+layerMatch[0].length).split(/[.!?;]/)[0];
        if(fields[lf].field!=='title' && /\b(?:previous(?:ly)?|earlier|historically|prior studies|past studies|before our)\b/i.test(beforeLayer.slice(-90)+' '+afterLayer.slice(0,50)))continue;
        if(/\b(?:no|not|without|neither|absence of|lack of)\b[^,;.!?]{0,55}$/i.test(beforeLayer) || /^[^,;.!?]{0,40}\b(?:not|never)\s+(?:observed|measured|performed|applied|detected|used|present)/i.test(afterLayer))continue;
        found.push(layerMatch[0]);
      }
      if(found.length){found.forEach(function(s){var prefix=s.toLowerCase().replace(/[- ]?layer$/,''),v=layerMap[prefix]||parseInt(prefix,10);if(layerValues.indexOf(v)<0)layerValues.push(v);});
        layerEvidence={id:'layers',label:'Layer counts mentioned',text:found.join(' / '),field:fields[lf].field,excerpt:fields[lf].text,derived:true};break;}
    }
    var layerCount = layerValues.length===1 ? layerValues[0] : null;
    if(layerEvidence) facts.push(layerEvidence);
    var ambient = evidence(/\bambient[- ]pressure\b|\bwithout (?:applied )?pressure\b|\bpressure[- ]free\b/i,true);
    if(ambient) facts.push({id:'ambient',label:'Ambient pressure mentioned',text:ambient.text,field:ambient.field,excerpt:ambient.excerpt});
    add('pressure', 'Pressure discussed', /\b(?:high|hydrostatic|extreme|external|applied)[- ]pressure\b|\bpressure[- ](?:induced|driven|quench|tuning)\b|\bdiamond[- ]anvil\b|\b\d+(?:\.\d+)?\s*GPa\b/i);
    // An ambient/no-pressure headline is the article's scope. Historical high-
    // pressure background must not turn that headline into an anvil experiment.
    if(ambient && ambient.field==='title' && !/\bquench\b/i.test(title)) facts=facts.filter(function(f){return f.id!=='pressure'||f.field==='title';});
    add('strain', 'Strain discussed', /\b(?:tensile|compressive|uniaxial|biaxial)?\s*strain(?:ed|ing|[- ]tunable)?\b/i);
    if(/\b(?:unstrained|strain[- ]free|without strain)\b/i.test(title)) facts=facts.filter(function(f){return f.id!=='strain';});
    add('doping', 'Carrier control discussed', /\b(?:electron|hole|chemical|electrostatic)[- ]dop(?:ed|ing)\b|\bdual[- ]gate\b|\bgat(?:e[- ]tunable|ing)\b/i);
    add('light', 'Electromagnetic probe / drive', /\bterahertz\b|\bmillimeter[- ]wave\b|\blaser\b|\blight[- ](?:induced|pulse|driven)\b|\bpicosecond\b/i);
    add('four-probe', 'Four-terminal method mentioned', /\bfour[- ](?:probe|terminal|point)\b/i);
    add('transport', 'Electrical transport discussed', /\bresistivit(?:y|ies)\b|\bresistance\b|\b(?:charge|electrical|electron|electronic) transport\b|\bcurrent[- ]voltage\b/i);
    add('magnetic', 'Magnetic response discussed', /\bmagneti[sz]ation\b|\b(?:magnetic|spin) susceptibilit(?:y|ies)\b|\bmagnetic field\b|\bmuon[- ]spin\b/i);
    add('thermal', 'Thermodynamics discussed', /\bspecific heat\b|\bheat capacit(?:y|ies)\b|\bcalorimetr\w*\b|\bthermodynamic\w*\b/i);
    add('spectrum', 'Spectroscopy discussed', /\bphotoemission\b|\bARPES\b|\btunnell?ing spectroscop\w*\b|\bRaman\b|\bneutron scattering\b|\bdensity of states\b|\bspectroscop\w*\b/i);
    add('generation', 'Structure proposal method', /\bdiffusion models?\b|\bgenerative\b|\binverse design\b|\bstructure search\b|\bguided diffusion\b/i);
    add('network', 'Learned representation / predictor', /\b(?:graph |line[- ]graph |deep |convolutional )?neural networks?\b|\bALIGNN(?:\s*2\.0)?\b|\bneural tangent kernels?\b|\bmachine[- ]learning\b|\bdeep learning\b/i);
    add('literature', 'Document / data method', /\bretrieval[- ]augmented\b|\bstructured extraction\b|\btext mining\b|\blanguage models?\b|\bliterature\b|\bdatabase\b/i);
    add('calculation', 'Theoretical / numerical method', /\bDFPT\b|\bDFT\b|\bEliashberg\b|\bfirst[- ]principles\b|\bexact diagonalization\b|\bdensity[- ]functional\b|\bHubbard\b|\bHamiltonian\b|\bBogoliubov\b|\bMonte Carlo\b/i);
    add('junction', 'Device geometry discussed', /\bJosephson junction\w*\b|\bquantum dots?\b|\bnanowire\w*\b|\bqubits?\b|\btransmons?\b|\bthree[- ]terminal\b/i);
    add('phonon', 'Lattice coupling discussed', /\belectron[-– ]phonon\b|\bphonon\w*\b|\bbreathing mode\b/i);
    add('vortex', 'Vortex response discussed', /\bvort(?:ex|ices)\b/i);
    add('gap', 'Pairing / gap question', /\b(?:nodeless|nodal|d[- ]wave|s[- ]wave|p[- ]wave|chiral|triplet)\b|\bpairing\b|\bsuperconducting gap\b/i);
    add('correlations', 'Correlations / competing order', /\bstripes?\b|\bcharge[- ]density[- ]wave\b|\bChern insulators?\b|\bcorrelat(?:ed|ions?)\b|\bnematic\w*\b|\bquantum critical\w*\b/i);
    add('boundary', 'Topology / boundary question', /\btopolog\w*\b|\bMajorana\b|\bedge states?\b|\bKitaev\b/i);
    var symbols = ('H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr').split(' ');
    var blocked = /^(?:BCS|BEC|DFT|DFPT|DOS|SOC|SC|AI|ML|THz|GHz|MHz|GPa|MPa|Pa|K|Tc|TA|PR|PI|US|UK|UN|SI|IS|AS|IT|ON|AT|IN|OR|AND|In|As|He|No|Bi|Fm)$/;
    var materials = [], materialSeen = {};
    fields.forEach(function (f) {
      var normalized = f.text.replace(/([A-Z][a-z]?)\s+(\d)/g, '$1$2').replace(/(\d)\s+([A-Z])/g, '$1$2');
      (normalized.match(/\b[A-Z][A-Za-z0-9]*(?:\.[0-9]+)?\b/g) || []).forEach(function (token) {
        if (blocked.test(token) || materialSeen[token] || token.length > 30) return;
        var parts = token.match(/[A-Z][a-z]?(?:\d+(?:\.\d+)?)?/g) || [];
        // Capitals alone (NUS, FP, II) are acronyms unless a count says otherwise.
        if (parts.join('') !== token || parts.length < 2 || !/[a-z\d]/.test(token) || parts.some(function (part) { return symbols.indexOf(part.match(/^[A-Z][a-z]?/)[0]) < 0; })) return;
        materialSeen[token] = true;
        materials.push({ text: token, field: f.field, components: parts.map(function (part) { var m = /^([A-Z][a-z]?)(.*)$/.exec(part); return { element: m[1], count: m[2] || '1' }; }) });
      });
    });
    var named = evidence(/\bgraphene\b|\bsamarium nickelates?\b|\bnickelates?\b|\bcuprates?\b|\bhydrides?\b|\bruthenates?\b|\biron[- ]based\b|\blithium[- ]6\b|\bHg[- ]1223\b|\bBi[- ]2223\b|\bkagome\b/i);
    var subjects = title.split(/\s+(?:in|of|using|via|under|through|with|from|for|and|on|over)\s+/i).map(function (x) { return x.trim().replace(/[.:;,]$/, ''); }).filter(function (x) { return x.length > 3; });
    // Text concepts are retained in sparse metadata cases rather than inventing
    // a sample or experiment. Different research questions remain different.
    var concepts = subjects.length ? subjects.slice(0, 5) : [title];
    var ids = facts.map(function (f) { return f.id; }), has = function (id) { return ids.indexOf(id) >= 0; };
    var modes = [['generation','generation'],['literature','documents'],['network','network'],['light','light'],['four-probe','transport'],
      ['transport','transport'],['spectrum','spectrum'],['thermal','thermal'],['magnetic','magnetic'],['junction','device'],['calculation','theory'],
      ['phonon','phonon'],['vortex','vortex'],['pressure','pressure'],['strain','strain'],['doping','carrier'],['layers','layers'],
      ['correlations','correlations'],['gap','pairing'],['boundary','boundary']];
    // A method/subject explicitly named in the headline has priority over a
    // keyword in abstract background. Body matches remain labelled mentions.
    var primary = modes.filter(function(pair){return facts.some(function(f){return f.id===pair[0] && f.field==='title';});})[0];
    if(!primary) primary=modes.filter(function(pair){return has(pair[0]);})[0];
    var mode = primary ? primary[1] : 'question';
    var theoretical = has('calculation') || /\b(?:theory|computation|theoretical|simulation|numerically exact|mean[- ]field|we compute|we calculate)\b/i.test(all+' '+(n.kind||n.k||''));
    var measured = evidence(/\b(?:we measure|measurements|experimentally|measured|synthesized|synthesised)\b/i,true);
    var negative = fields.some(function(f){return f.text.split(/[.!?;]/).some(function(sentence){
      if(f.field!=='title' && /\b(?:previous(?:ly)?|earlier|historically|before|prior)\b/i.test(sentence))return false;
      return /\b(?:no|absence of|not observed|not detected)\s+(?:evidence (?:for|of)\s+)?superconductivity\b|\bsuperconductivity\s+(?:was |is |has been )?(?:not observed|not detected|absent)\b/i.test(sentence);
    });});
    var stage = negative ? 'Negative claim in source; tested conditions matter' :
      /\b(?:predict(?:ed|ion|s)?|propos(?:ed|al))\b/i.test(title) || n.ai_kind === 'prediction' || n.ai_kind === 'generation' ? 'Prediction / theory described; not experimental proof' :
      theoretical ? (measured ? 'Models and measurements mentioned; check their roles in the source' : 'Theory / computation discussed; not experimental proof') :
      measured ? 'Measurements mentioned; consult the source for criteria' : 'Evidence status is not established by this feed';
    var src = n.url || '', ref = n.ref && typeof REFS !== 'undefined' && REFS[n.ref];
    if (!src && ref) src = ref.url || ref.u || (ref.d ? 'https://doi.org/' + ref.d : '');
    if(/^http:\/\/(?:link\.aps\.org|dx\.doi\.org|doi\.org)\//i.test(src)) src=src.replace(/^http:/,'https:');
    if (!src && /^10\.\d+\//.test(n.doi || '')) src = 'https://doi.org/' + n.doi;
    var key = String(n.doi || n.url || n.id || n.ref || title);
    var result = { key: key, title: title, source: String(n.source || n.journal || 'Linked source'), url: src,
      materials: materials.slice(0, 4), namedSubject: named ? named.text : '', layerCount: layerCount, layerCounts: layerValues,
      facts: facts, concepts: concepts, mode: mode, evidence: stage, sparse: !n.summary && !n.abstract && !n.x,
      scope: 'Source-based schematic. Geometry, motion and connections are illustrative; no measured curve or crystal coordinates are reconstructed.' };
    result.signature = JSON.stringify({ materials: result.materials.map(function (m) { return m.text; }), layers: layerValues,
      mode: mode, facts: facts.map(function (f) { return [f.id, f.text.toLowerCase()]; }), concepts: concepts });
    return result;
  };

  // A compact neutral fallback for an unregistered theme. The original topic
  // animations take priority in miniFrame; this icon invents no article data.
  const newsArticleDraw = function newsArticleDraw(c, C, W, H, t, info) {
    var k = Math.min(W / 112, H / 84), x = W / 2 - 20 * k, y = H / 2 - 27 * k;
    c.strokeStyle = C.accent || C.ink || '#456'; c.lineWidth = 1.4; c.lineCap = 'round';
    c.strokeRect(x, y, 40 * k, 54 * k);
    for (var row = 0; row < 4; row++) {
      c.globalAlpha = .45 + .35 * (1 + Math.sin(t * 1.3 - row)) / 2;
      c.beginPath(); c.moveTo(x + 8 * k, y + (12 + row * 10) * k);
      c.lineTo(x + (row === 3 ? 24 : 32) * k, y + (12 + row * 10) * k); c.stroke();
    }
    c.globalAlpha = 1;
  };

  // Further subjects an article names itself, in the order it names them, for a page that
  // already shows its first subject. Alternatives come only from the article's headline,
  // summary, headline formula, feed topics or curated material cards; a pairing state needs
  // its own word (d-wave, triplet, time-reversal), and a retraction or null result keeps
  // only the neutral icon. A summary counts only in specific wording: a bare "gap", "film",
  // "magnet", "wire" or "phase diagram" there says too little to draw, and a headline with
  // no subject of its own borrows none from its summary.
  const newsArtChoices = function newsArtChoices(item, info, primary) {
    var n = item || {}, out = [primary], head = String(n.title || n.h || ''), text = String(n.summary || n.x || '') + ' ' + String(n.abstract || '');
    if (primary === 'news-research' && /retract|withdrawn|debunk|no superconductivity|not superconduct|absence of superconductivity/i.test(head)) return out;
    var add = function (kind) { kind = 'news-' + kind; if (out.indexOf(kind) < 0) out.push(kind); };
    var clean = function (s) {
      return s.replace(/\bambient[- ]pressure\b|\b(?:without|no)\s+(?:applied\s+|external\s+)?pressure\b|\bpressure[- ]free\b|\b(?:partial|vapou?r|gas|chemical|base|background|chamber|growth|oxygen|O\s?[₂2]|N\s?[₂2]|argon)\s+pressures?\b|\bpressures? of [^.;]{0,30}?\b(?:Torr|mbar|Pa)\b/gi, '')
        .replace(/\b(?:without|no|absence of)\s+(?:a\s+)?moir[eé](?:\s+pattern)?\b/gi, '')
        .replace(/\b(?:spin|band|charge[- ]transfer|Mott|Haldane|optical)\s+gaps?\b|\bin-gap\b|\bbridg\w* (?:the|this|a) gap\b|\bgaps? between\b/gi, '')
        // The textbook definition ("superconductors carry current with zero resistance") is no measurement.
        .replace(/\b(?:carr(?:y|ies|ying)|conduct(?:s|ing)?)\b[^.;]{0,40}?(?:\b(?:zero|no)\s+(?:electrical\s+)?resistance|\bresistance of zero)\b/gi, '');
    };
    // Each cue: headline wording, subject, then the stricter wording a summary needs (null: headline only).
    var cues = [[/vort(?:ex|ices)|fluxons?|Abrikosov/i, 'vortex', /vort(?:ex|ices)(?![- ]free)|fluxons?|Abrikosov/i],
      [/pressur(?:e|i[sz]ed|i[sz]ing)|\bGPa\b|diamond[- ]anvil|squeez/i, 'pressure'],
      [/hydrides?\b|superhydride|\b(?:La|Ce|Y|Ca|Sc|Lu)H\d|\bH\s?[₃3]\s?S\b/i, 'hydride'], [/bilayer nickelate|Ni\s?[₂2]\s?O\s?[₇7]/i, 'nickelate'],
      [/nickelate|infinite[- ]layer/i, 'layered'], [/cuprate|CuO\s?[₂2]|\bYBCO\b|\bYBa|\bBi-?22\d\d|\bHg-?12\d\d|\bLSCO\b/i, 'cuprate'],
      [/iron[- ](?:based|pnictide|chalcogenide)|pnictide|\bFe(?:Se|As|Te)/i, 'iron'], [/kagome/i, 'kagome'],
      [/heavy[- ]fermion|Kondo|\bU(?:Te|Ru|Pt)|\bCe(?:Rh|Co|Ir|Cu)|\bYbRh/i, 'heavy'],
      [/\btriplet\b/i, 'triplet', /spin[- ]triplet|triplet (?:pairing|superconduct|order parameter|component)|odd[- ]parity (?:pairing|superconduct)/i],
      [/twist|moir[eé]|magic[- ]angle/i, 'moire', /twisted (?:bilayer|trilayer|double|mono|multi|graphene|WSe|MoTe|homo|hetero)|moir[eé]|magic[- ]angle/i],
      [/graphene|rhombohedral/i, 'layered'],
      [/topological|Majorana|Kitaev/i, 'topo', /topological (?:superconduct|phase|state|insulator|qubit|band|edge|surface|crystalline)|Majorana|Kitaev/i],
      [/phonons?\b(?![- ](?:mediated )?detectors?)(?![- ]pulses?)|polaron|isotope effect|electron[- ]boson/i, 'eph',
        /electron[- ]phonon|phonon[- ]mediated|polarons?|isotope effect|electron[- ]boson|(?:soft|optical|acoustic|Raman[- ]active) phonons?|phonon (?:softening|anomal|dispersion|frequenc|modes?|drag)/i],
      [/Josephson|junctions?\b|weak links?/i, 'junction'],
      [/qubits?|transmon|quantum (?:computer|computing|processor|information)/i, 'qubit', /qubits?|transmons?/i],
      [/stripes?(?![- ]domain)|charge order|charge[- ]density[- ]wave|\bCDW\b|Hubbard/i, 'stripes', /charge stripes?|stripe (?:order|phase|state|correlation)s?|superconducting stripes|stripes? and superconduct|charge[- ]order|charge[- ]density[- ]wave|\bCDW\b/i],
      [/spin[- ]fluctuat|magnon|paramagnon|spin waves?/i, 'spinfluct'],
      [/\bd[- ]wave\b/i, 'dwave'], [/nodeless|multi[- ]?gap|two[- ]gap|multi[- ]?band|\bs\s?±|\bs\+-/i, 'multigap'],
      [/\bgaps?\b|pseudogap/i, 'gapdos', /superconducting (?:energy )?gaps?|pairing gaps?|pseudogap|coherence peaks?|gap[- ]to[- ]T\s?c|(?:extracted|measured|full|fully open|outer[- ]plane|inner[- ]plane|nodal|nodeless|isotropic|anisotropic) (?:s-wave )?gaps?\b|\bgaps?\b[^.;]{0,25}?\d+(?:\.\d+)?\s?meV|nodes in the gap/i],
      [/pair[- ]density[- ]waves?|FFLO|finite[- ]momentum pair/i, 'fflo'],
      [/time[- ]reversal(?:[- ]symmetry)?[- ](?:symmetry[- ])?break|break\w* (?:the )?time[- ]reversal|broken (?:[\w-]+ (?:and|or) )?time[- ]reversal|\bTRSB\b|chiral (?:[\w-]+[- ])?superconduct/i, 'trsb'],
      [/diodes?\b|non-?reciprocal|magnetochiral/i, 'diode'], [/detectors?\b|photon detection|bolometer|\bSNSPD/i, 'detector'],
      [/superconducting magnets?|\b(?:fusion|MRI|accelerator|high[- ]field|REBCO|HTS|Nb\s?[₃3]\s?Sn|NbTi)\s+(?:magnets?|coils?)\b|\b(?:model|magnet|insert|test)\s+coils?\b|\bsolenoids?\b|\bfusion\b|tokamak/i, 'coil'],
      [/\bcables?\b|\bpower (?:lines?|cables?|transmission)|current leads?|coated conductors?|\btapes?\b|superconducting wires?/i, 'cable'],
      [/\brings?\b|Little[- ]Parks|\bSQUIDs?\b|flux(?:oid)? quantiz/i, 'ring', /superconduct\w* (?:rings?|loops?)|\brings? of\b|\bannul|Little[- ]Parks|\bSQUIDs?\b|flux(?:oid)? quantiz/i],
      [/(?:optical|dark|photonic|terahertz|THz|infrared) cavit|cavit(?:y|ies)[- ](?:QED|quantum electrodynamics|photons?|vacuum|modes?|materials?|enhanced|controlled|induced|altered|embedded)|Casimir|polaritons?|vacuum[- ]fluctuation/i, 'cavity'],
      [/resonators?|transmission lines?|kinetic[- ]inductance|microwave (?:resonator|cavit|circuit|measurement|photon)|coplanar waveguide/i, 'resonator'],
      [/\bSRF\b|accelerat\w* cavit|radio[- ]frequency cavit|cryomodule/i, 'rf'],
      [/cold atoms?|ultracold|optical lattices?|quantum gas|atomic Fermi gas|trapped atoms?/i, 'coldatoms'],
      [/penetration depths?(?! of the (?:pump|probe|light|laser))|superfluid (?:density|stiffness)|coherence lengths?|Meissner|field screening/i, 'penetration'],
      [/proximit/i, 'proximity'], [/thermal (?:transport|conductiv|Hall)|thermoelectric|Nernst|heat (?:flow|transport|conduction)/i, 'thermal'],
      [/competi(?:tion|ng)|rivalry|coexist|intertwined|tetracritic|two (?:superconducting |competing |quantum )?(?:phases|orders|states|flavou?rs)(?! of magnitude)/i, 'competition',
        /compet(?:ing|ition between|ition of|ition with) (?:[\w-]+ ){0,3}(?:orders?|phases?|states?|superconduct)|(?:superconductivity|orders?|magnetism|phases) co-?exist|co-?existence (?:of|between) (?:[\w-]+ ){0,3}(?:superconduct|orders?|magnetism|phases?)|intertwined (?:[\w-]+ ){0,2}orders?|tetracritic|rivalry|two (?:superconducting |competing |quantum |distinct )?(?:phases|orders|states|flavou?rs)(?! of magnitude)/i],
      [/antiferromagnet|ferromagnet|magnetism|magnetic order|altermagnet/i, 'magnetism'],
      [/single[- ]molecule|molecules? (?:on|adsorbed)|molecular (?:spin|magnet|chain|layer)|Shiba|\bYSR\b|\bmagnetic (?:impurit|adatom)|adatoms?/i, 'molecule'],
      [/domain walls?|heterogene|inhomogene|granular|puddles?|mosaic|patchwork/i, 'domains', /domain walls?|(?:heterogene|inhomogene)\w* (?:superconduct|state|T\s?c|pairing|order)|granular|puddles?|mosaic|patchwork/i], [/\bdisorder|\bdirty\b/i, 'disorder'],
      [/\bdomes?\b/i, 'dome'], [/re-?entrant|\brevives?\b|field[- ](?:boosted|stabili[sz]ed|induced superconduct)/i, 'reentrant'],
      [/quasiparticle interference|\bQPI\b|\bripples?\b/i, 'qpi'], [/Andreev/i, 'andreev'], [/Zhang[– -]Rice/i, 'zr'], [/apical/i, 'apical'],
      [/\bcylinders?\b/i, 'cylinder', /-leg (?:[\w-]+ )?(?:ladders?|cylinders?)|(?:Hubbard|t-J|lattice|square) cylinders?|cylinders? of (?:width|circumference)/i],
      [/neural[- ]network (?:quantum states?|wave ?functions?)/i, 'nqs'],
      [/Zeeman|Ising superconduct|Pauli[- ]limit|spin[- ]imbalanc/i, 'zeeman'], [/kekul/i, 'kekule']];
    // Sample forms come after named subjects and families, from the headline only; measurement and method words come last.
    var forms = [[/multilayer|few[- ]layer|\bbilayer\b|\btrilayer\b|van der Waals/i, 'layered'], [/interfaces?|heterostructures?|thin[- ]films?|\bfilms?\b|epitax|substrates?/i, 'interface'],
      [/monolayer|atomically thin|single[- ]layer|two-dimensional|\b2D\b/i, 'monolayer']];
    var generic = [[/terahertz|\blasers?\b|ultrafast|picosecond|femtosecond|\blight\b(?![- ]?weight)|photo-?(?:galvanic|current|induced)|optical (?:pump|driv|excit)/i, 'light',
        /terahertz|ultrafast|picosecond|femtosecond|light[- ](?:induced|driven)|photo-?(?:galvanic|current|induced)|optical(?:ly)? (?:pump|driv|excit)|laser (?:pulse|pump|driv|excit)/i],
      [/spectroscop|\bRaman\b|neutron|\bmuons?\b|\bNMR\b|\bARPES\b|photoemission|density of states|ultrasound|ultrasonic|sound velocit/i, 'spectrum',
        /spectroscop|\bRaman\b|neutron|\bmuons?\b|\bNMR\b|\bARPES\b|photoemission|ultrasound|ultrasonic|sound velocit/i],
      [/resistiv|resistance|electrical transport|critical current|zero[- ]resistance/i, 'measurement'],
      [/graph neural|\bALIGNN|crystal graph/i, 'graph'],
      [/\bgenerative\b|generat(?:e|es|ed|ing) (?:new |novel |candidate |stable |hypothetical )?(?:[\w-]+ )?(?:materials|crystals|structures|compounds|candidates|superconductors)\b|diffusion models?|inverse design|structure (?:search|prediction)|AI-proposed|propos(?:e|es|ed) (?:[\d.,]+ (?:million |thousand )?)?(?:new |stable |novel )?(?:crystals|materials|structures|candidates|superconductors)\b/i, 'search'],
      [/language models?|\bLLMs?\b|literature|text mining|\bdatabases?\b|retrieval[- ]augmented|structured extraction/i, 'literature',
        /language models?|\bLLMs?\b|text[- ]mining|literature[- ](?:mining|extraction|search|derived|data)|retrieval[- ]augmented|structured extraction|\bdatabases?\b/i],
      [/boosted trees?|gradient[- ]boost|random forest|decision trees?/i, 'tree'],
      [/conformal|prediction intervals?|\buncertaint/i, 'interval', /conformal|prediction intervals?|(?:predictive|prediction|model|calibrated) uncertaint|uncertainty (?:quantification|estimate|band|interval)/i],
      [/\brout(?:er|ing)\b/i, 'routing'], [/two parts|two[- ]stage/i, 'two-stage', null],
      [/machine[- ]learning|deep learning|neural networks?|\bAI\b|data[- ]driven/i, 'features'],
      // A retrospective is a headline subject; years mentioned in a summary are background.
      [/\b\d+[- ]years?\b|anniversary|decades?|history of/i, 'timeline', null]];
    // Only a plain statement counts: a negated, hedged, historical or comparative mention in the
    // same sentence ("whether ... is not established", "earlier work", "cuprate-like", "for
    // comparison") never selects a subject, nor, in a summary, an aside or an outlook
    // ("applications such as", "could one day", "reduces proximity effects", "opens possibilities").
    var negated = /\b(?:no|not|without|neither|nor|absence of|lack of|whether|unclear|unknown|ruled? out|previous(?:ly)?|earlier|originally|long been|inconsistent|against|for comparison)\b/i,
      aside = /\b(?:could|would|might|may|possibl[ey]|potential(?:ly)?|promising|applications?|such as|including|e\.g\.|like|unlike|as in|similar to|compared (?:to|with)|often|usually|commonly|typically|reported|beyond|central to|reduc\w*|suppress\w*|avoid\w*|eliminat\w*)\b/i,
      outlook = /\b(?:open\w* (?:up )?(?:new )?(?:possibilit|avenue|route|pathway|door)|pav\w* the way|future|prospect|outlook)/i,
      modal = /^\W*(?:\w+\W+){0,3}?(?:could|can|would|may|might|ha(?:ve|s) become)\b/i;
    var positive = function (s, re, body) {
      var g = new RegExp(re.source, re.flags.replace('g', '') + 'g'), m;
      while ((m = g.exec(s))) {
        var before = s.slice(0, m.index).split(/[.!?;]/).pop(), after = s.slice(m.index + m[0].length).split(/[.!?;]/)[0];
        if (!negated.test(before.slice(-80) + ' ' + after.slice(0, 60)) && !/\bnon-?$|\blike\s*$/i.test(before) &&
          !(body && (aside.test(before.slice(-40)) || outlook.test(before) || modal.test(after)))) return m.index;
        if (!m[0].length) g.lastIndex++;
      }
      return -1;
    };
    var scan = function (s, table, body) {
      var hits = [];
      table.forEach(function (cue, order) { var re = body && cue.length > 2 ? cue[2] : cue[0], at = re ? positive(s, re, body) : -1; if (at >= 0) hits.push([at, order, cue[1]]); });
      hits.sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; }).forEach(function (hit) { add(hit[2]); });
    };
    var h1 = clean(head), t1 = clean(text), els = {};
    scan(h1, cues);
    info.materials.forEach(function (m) { if (m.field === 'title') m.components.forEach(function (c) { els[c.element] = (els[c.element] || 0) + (parseFloat(c.count) || 1); }); });
    if (els.Cu && els.O) add('cuprate');
    if (els.Ni && els.O) add(/Ni\s?[₂2]\s?O\s?[₇7]|bilayer/i.test(head + ' ' + text) ? 'nickelate' : 'layered');
    if (els.Fe && (els.As || els.Se || els.Te || els.P || els.S)) add('iron');
    if (els.H >= 3) add('hydride');
    if ((els.V && els.Sb) || (els.Ti && els.Bi)) add('kagome');
    if (els.U || els.Ce || els.Yb) add('heavy');
    if (els.Mg && els.B) add('multigap');
    if ((els.Nb || els.Ta || els.Mo || els.W) && (els.Se || els.S || els.Te)) add('layered');
    var topics = { Hydrides: 'hydride', Cuprates: 'cuprate', 'Iron-based': 'iron', Kagome: 'kagome', 'Heavy fermions': 'heavy', Topological: 'topo',
      'Electron–phonon': 'eph', 'Moiré and 2D': 'layered', Nickelates: 'layered', 'Quantum devices': 'qubit', 'AI and data': 'features' };
    var cards = { hydride: 'hydride', nickelate: 'nickelate', iron: 'iron', rebco: 'cuprate', hg1223: 'cuprate', heavy: 'heavy', mgb2: 'multigap',
      josephson: 'junction', topo: 'topo', magnet: 'coil', london: 'penetration', gl: 'vortex', bcs: 'eph', eliashberg: 'eph', moire: 'moire', magic: 'moire' };
    var phononText = /electron[- –]phonon|phonon|Eliashberg|McMillan|Allen[- ]Dynes|MgB\s?[₂2]|Nb\s?[₃3]\s?Sn|NbTi|\bconventional superconduct/i.test(head + ' ' + text);
    list(n.topics).forEach(function (t) { if (topics[t] && (t !== 'Electron–phonon' || phononText)) add(topics[t]); });
    list(n.cards).forEach(function (c) { if (cards[c]) add(cards[c]); });
    scan(h1, forms);
    scan(h1, generic);
    var lead = out.length;
    if (primary !== 'news-research') { scan(t1, cues, true); scan(t1, generic, true); }
    // Last resort before repeating a subject on the page: the neutral page icon, which asserts nothing.
    add('research');
    // A second drawing of a headline subject, where one exists, comes after the other headline
    // subjects and before subjects named only in the summary; the page icon's comes last.
    var table = typeof MINI_DRAW !== 'undefined' && MINI_DRAW, all = [];
    var keep = function (k) { return k === primary || !table || typeof table[k] === 'function'; };
    // A second drawing that shows something more specific is offered only when the article's words allow it.
    var only = { 'news-topo': /Majorana|Kitaev|zero[- ](?:energy |bias )?modes?|nanowire/i, 'news-tree': /^(?![\s\S]*random forest)/i,
      'news-trsb': /chiral|domains?\b/i, 'news-spinfluct': /^(?![\s\S]*\bferromagnet)/i, 'news-junction': /Josephson|weak links?|SQUID/i };
    var twin = function (k) { if (table && typeof table[k + '-2'] === 'function' && (!only[k] || only[k].test(h1 + ' ' + t1))) all.push(k + '-2'); };
    out.slice(0, lead).filter(keep).forEach(function (k) { all.push(k); });
    out.slice(0, lead).filter(keep).forEach(twin);
    out.slice(lead).filter(keep).forEach(function (k) { all.push(k); twin(k); });
    return all;
  };

  // One look per article and theme for the session. A badge comes only from the
  // article's own wording: the headline first, then facts that passed the negation
  // and history checks. Colour set and framing are neutral variants, assigned in
  // turn, so thumbnails that share a theme are never drawn alike.
  const newsArtLook = function newsArtLook(item, info, kind) {
    var reg = MINI.looks || (MINI.looks = { ids: Object.create(null), n: Object.create(null) }), id = kind + '\n' + info.key;
    if (reg.ids[id]) return reg.ids[id];
    var i = reg.n[kind] || 0, hash = 2166136261, head = info.title, bare = String(kind).replace(/^news-/, '').replace(/-2$/, ''), parts = [];
    reg.n[kind] = i + 1;
    for (var q = 0; q < info.key.length; q++) hash = Math.imul(hash ^ info.key.charCodeAt(q), 16777619) >>> 0;
    var look = { v: i % 6, p: (i + Math.floor(i / 12)) % 4, ph: hash % 1000 / 160, notice: '', probe: '', from: '', comp: [], formula: '', tc: 0, gpa: 0, tesla: 0, text: '' };
    var probes = [['stm', /\bSTM\b|\bSTS\b|scanning[- ]tunnell?ing|tunnell?ing (?:microscop|spectroscop)|quasiparticle interference|\bQPI\b/i],
      ['arpes', /\bARPES\b|photo-?emission/i], ['neutron', /\bneutrons?\b/i], ['muon', /\bmuons?\b|[μµ]SR\b|\bmuSR\b/i],
      ['nmr', /\bNMR\b|\bNQR\b|nuclear magnetic resonance|Knight shift/i], ['raman', /\bRaman\b/i],
      ['xray', /\bX-ray|\bRIXS\b|diffraction|synchrotron|tomograph|3D imaging/i],
      ['optics', /optical (?:\w+ )?(?:conductivit|respons|Hall|absorption|spectroscop)|reflectivit|infrared|\bTHz\b|terahertz|millimet(?:er|re)[- ]wave|ellipsometr/i],
      ['pulse', /\blasers?\b|ultrafast|picosecond|femtosecond|pump[- ]probe|light[- ](?:induced|driven|pulse)|optical(?:ly)? (?:pump|driv)|Floquet/i],
      ['anvil', /diamond[- ]anvil|\bGPa\b|(?:high|hydrostatic|extreme|external|applied)[- ]pressure|pressur(?:i[sz]ed|e[- ](?:induced|driven|quench|tuning))|under pressure|squeez/i],
      ['strain', /\bstrain(?:ed|ing)?\b/i],
      ['field', /magnetic[- ]fields?|\btesla\b|\bhigh[- ]fields?\b|field[- ](?:induced|boosted|stabili[sz]ed|tuned|tunable)|magneti[sz]ation|susceptibilit/i],
      ['heat', /specific heat|heat capacit|calorimetr|thermal (?:conductivit|transport)|thermoelectric|Nernst/i],
      ['contacts', /resistiv|resistance|electrical transport|magnetotransport|critical current|Hall (?:effect|resistance|response)|current[- ]voltage|four[- ](?:probe|terminal)/i],
      ['gate', /\bgat(?:e|ed|ing)\b|electrostatic|ionic[- ]liquid|field[- ]effect/i],
      ['dope', /\bdop(?:ed|ing|ants?)\b|substitution|intercalat|oxygen content/i],
      ['calc', /\bDFT\b|density[- ]functional|first[- ]principles|ab initio|Eliashberg|\bDMRG\b|Monte Carlo|exact diagonali|tensor[- ]network|numerics?\b|numerical|simulations?\b|mean[- ]field|calculat(?:ions?|ed|ing)\b|comput(?:ed|ations?|ational)\b/i],
      ['ml', /machine[- ]learning|neural|deep learning|language models?|generative|\bAI\b/i],
      ['phonon', /phonons?|electron[- ]boson|lattice vibration/i],
      ['device', /\bdevices?\b|\bjunctions?\b|\bqubits?\b|\bSQUIDs?\b|nanowires?|transmons?/i],
      ['edge', /topological|Majorana|edge (?:states?|modes?|currents?)/i],
      ['film', /\bfilms?\b|epitax|\bMBE\b|heterostructures?|substrates?/i]];
    // A badge that repeats what the theme already draws adds clutter, not information.
    var skip = { stm: /^(?:qpi|gapdos)$/, anvil: /^pressure$/, pulse: /^(?:light|cavity)$/, optics: /^(?:light|cavity)$/,
      field: /^(?:coil|cable|zeeman|penetration|vortex|ring|reentrant)$/, heat: /^thermal$/, contacts: /^(?:measurement|diode)$/,
      ml: /^(?:features|graph|search|literature|tree|interval|routing|two-stage|ai|nqs)$/, phonon: /^eph$/,
      device: /^(?:junction|qubit|andreev|diode|detector|ring|resonator)$/, edge: /^topo$/, film: /^(?:interface|monolayer)$/ };
    var usable = function (pid) { return !(skip[pid] && skip[pid].test(bare)); };
    look.notice = /^(?:(?:author|publisher)(?:['’]s)? )?(?:correction|erratum|corrigendum)\b/i.test(head) ? 'fix' :
      /^(?:reply|response|comment)\b/i.test(head) ? 'reply' : /^addendum\b/i.test(head) ? 'add' :
      /^retraction\b|\bretract(?:ed|ion|s)?\b|expression of concern/i.test(head) ? 'retract' : '';
    var scan = head.replace(/\bambient[- ]pressure\b|\b(?:without|no)\s+(?:applied\s+|external\s+)?pressure\b|\bpressure[- ]free\b|\b(?:partial|vapou?r|gas)\s+pressures?\b/gi, '');
    for (var a = 0; a < probes.length && !look.probe; a++) if (probes[a][1].test(scan) && usable(probes[a][0])) { look.probe = probes[a][0]; look.from = 'title'; }
    var byFact = { spectrum: 'spectro', pressure: 'anvil', strain: 'strain', light: 'pulse', magnetic: 'field', thermal: 'heat', 'four-probe': 'contacts', transport: 'contacts',
      doping: 'dope', calculation: 'calc', network: 'ml', generation: 'ml', literature: 'ml', phonon: 'phonon', junction: 'device', boundary: 'edge' };
    // Body facts: a sample condition first, then a measurement, a drive, a device and finally a method.
    var rank = ['pressure', 'spectrum', 'magnetic', 'thermal', 'light', 'strain', 'four-probe', 'transport', 'doping', 'junction', 'phonon', 'calculation', 'network', 'generation', 'literature', 'boundary'];
    info.facts.filter(function (f) { return f.field !== 'title' && byFact[f.id]; }).sort(function (x, y) { return rank.indexOf(x.id) - rank.indexOf(y.id); }).forEach(function (f) {
      if (look.probe) return;
      var pid = byFact[f.id], generic = pid;
      for (var b = 0; b < probes.length; b++) if (probes[b][1].test(f.text) || probes[b][1].test(f.excerpt || '')) { pid = probes[b][0]; break; }
      if (!usable(pid)) pid = generic;
      if (usable(pid)) { look.probe = pid; look.from = f.field; }
    });
    var mat = info.materials.filter(function (m) { return m.field === 'title'; })[0];
    if (mat) {
      look.formula = mat.text;
      look.comp = mat.components.slice(0, 4).map(function (x) { return { el: x.element, n: Math.max(.2, parseFloat(x.count) || 1) }; });
    }
    var tc = /(?:^|[^\w.])(\d+(?:\.\d+)?)\s?(m?K)(?![-\w])/.exec(head), gpa = /(\d+(?:\.\d+)?)\s?GPa(?![-\w])/.exec(head), tesla = /(\d+(?:\.\d+)?)\s?(?:T|tesla)(?![-\w])/.exec(head);
    if (tc) look.tc = parseFloat(tc[1]) / (tc[2] === 'mK' ? 1000 : 1);
    if (gpa) look.gpa = parseFloat(gpa[1]);
    if (tesla) look.tesla = parseFloat(tesla[1]);
    var names = { stm: 'scanning-tunnelling tip', arpes: 'photoemission', neutron: 'neutron scattering', muon: 'muon spin rotation', nmr: 'nuclear magnetic resonance',
      raman: 'Raman scattering', xray: 'X-ray probe', optics: 'optical spectroscopy', pulse: 'light pulse', anvil: 'pressure cell', strain: 'strain', field: 'magnetic field',
      heat: 'heat measurement', contacts: 'electrical contacts', gate: 'electrostatic gate', dope: 'chemical substitution', calc: 'calculation', ml: 'machine-learning model',
      phonon: 'lattice vibration', device: 'device', edge: 'boundary current', film: 'thin film', spectro: 'spectroscopy',
      fix: 'correction notice', reply: 'reply or comment', add: 'addendum', retract: 'retraction' };
    if (look.notice) parts.push('Badge: ' + names[look.notice] + '.');
    else if (look.probe) parts.push('Badge: ' + names[look.probe] + ', named in the ' + look.from + '.');
    if (look.formula) parts.push('Element dots: ' + look.comp.map(function (x) { return x.el; }).join(', ') + ' from ' + look.formula + ' in the title.');
    if (tc) parts.push('Thermometer: ' + tc[1] + ' ' + tc[2] + ' in the title, on a logarithmic scale.');
    parts.push('Colours and framing only tell thumbnails apart.');
    look.text = parts.join(' ');
    reg.ids[id] = look;
    return look;
  };

  const newsArticleFigure = function newsArticleFigure(item, kind) {
    var info = newsArticleDescribe(item);
    var primary = kind || (item.ai_kind && typeof aiArticleArt === 'function' ? aiArticleArt(item) : newsArt(item)), shown = {};
    // A subject already on the page gives way to the next subject this article names.
    list(MINI.items).forEach(function (it) { if (it.article && it.cv && it.cv.isConnected) shown[it.kind] = true; });
    info.item = item; info.choices = newsArtChoices(item, info, primary);
    var art = info.choices.filter(function (k) { return !shown[k]; })[0] || primary;
    info.look = newsArtLook(item, info, art);
    return h('div', { class: 'news-art', 'data-article-key': info.key, 'data-source-url': info.url,
      title: info.title }, miniCanvas(art, item, info));
  };

  // Thumbnails are settled in page order: each takes its first subject that no thumbnail above
  // it shows, so lists filled at different times end alike. When every subject an article names
  // is already shown, an article above it moves to another subject that article names, if a
  // chain of such moves frees one (as in bipartite matching). Only then does a subject repeat,
  // and then one that the article's own list does not show yet, where the article names one.
  // A redrawn article keeps its look for each subject.
  const newsArtAssign = function newsArtAssign() {
    var items = list(MINI.items).filter(function (it) { return it.article && it.article.choices && it.cv && it.cv.isConnected; }), owner = {}, pick = [], loose = [];
    if (items.length > 1 && items[0].cv.compareDocumentPosition) items.sort(function (a, b) { return a.cv === b.cv ? 0 : a.cv.compareDocumentPosition(b.cv) & 4 ? -1 : 1; });
    var take = function (i, k) { if (owner[pick[i]] === i) delete owner[pick[i]]; pick[i] = k; owner[k] = i; };
    // Move article i to another subject it names, first a free one, else one whose owner can move.
    // An article is never moved onto the neutral page icon to make room for another.
    var move = function (i, seen) {
      var ch = items[i].article.choices.filter(function (k) { return !/^news-research/.test(k); }), a;
      for (a = 0; a < ch.length; a++) if (owner[ch[a]] === undefined) { take(i, ch[a]); return true; }
      for (a = 0; a < ch.length; a++) {
        var k = ch[a], j = owner[k];
        if (j === i || seen[k]) continue;
        seen[k] = true;
        if (move(j, seen)) { take(i, k); return true; }
      }
      return false;
    };
    items.forEach(function (it, i) {
      var ch = it.article.choices, seen = {}, a;
      for (a = 0; a < ch.length; a++) if (owner[ch[a]] === undefined) { take(i, ch[a]); return; }
      for (a = 0; a < ch.length; a++) {
        var k = ch[a];
        if (seen[k]) continue;
        seen[k] = true;
        if (move(owner[k], seen)) { take(i, k); return; }
      }
      loose.push(i);
    });
    var box = items.map(function (it) { return typeof it.cv.closest === 'function' ? it.cv.closest('ol') : null; });
    loose.forEach(function (i) {
      var near = {}, ch = items[i].article.choices, open;
      items.forEach(function (_it, j) { if (j !== i && pick[j] && box[j] === box[i]) near[pick[j]] = true; });
      open = ch.filter(function (k) { return !near[k]; });
      // The neutral page icon stands in only when the article names nothing else its list lacks.
      pick[i] = open.filter(function (k) { return !/^news-research/.test(k); })[0] || open[0] || ch[0];
    });
    items.forEach(function (it, i) {
      var info = it.article, kind = pick[i];
      if (kind === it.kind) return;
      it.kind = kind;
      info.look = newsArtLook(info.item, info, kind);
      it.cv.setAttribute('data-news-art', kind);
      it.cv.setAttribute('aria-label', info.title + '. ' + (MINI_ALT[kind] || 'Research-paper illustration; no material structure or measured result is depicted.') + ' ' + info.look.text + ' ' + info.evidence);
    });
  };
