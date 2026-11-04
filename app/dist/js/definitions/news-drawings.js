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
    if (/\bdiodes?\b|non-?reciprocal|rectification/i.test(head)) return 'news-diode';
    if (/stripes?(?![- ]domain)|Hubbard|Kondo[- ]Heisenberg/i.test(head)) return 'news-stripes';
    if (/geometry of materials|common features|representation|tangent kernel/i.test(head)) return 'news-features';
    if (/density of states|spectroscop|Raman|muon stopping|ultrasound/i.test(head)) return 'news-spectrum';
    // A twisted-light vortex beam is an optical probe, not flux vortices in the sample.
    if (/optical vort|vortex beams?|vortex light/i.test(head)) return 'news-light';
    if (/vort(?:ex|ices)|fluxons?|Abrikosov/i.test(head)) return 'news-vortex';
    if (/graphene/i.test(head)) {
      var grapheneText = body.replace(/\b(?:without|no|absence of)\s+(?:a\s+)?moir[eé](?:\s+pattern)?\b/gi, '');
      if (/twist|moir[eé]|magic[- ]angle/i.test(grapheneText)) return 'news-moire';
      return /(?:six|6)[- ]layer|hexalayer/i.test(head) ? 'news-layered-six' : 'news-layered';
    }
    if (/electron[– -]phonon|phonon|breathing mode|\bbipolarons?\b|\bpolarons?\b/i.test(head) && !/qubit|transmon/i.test(head)) return 'news-eph';
    if (/magnon|spin wave|spin[- ]fluctuat|paramagnon/i.test(head) && !/circuit|qubit/i.test(head)) return 'news-spinfluct';
    if (/graph neural|line[- ]graph|ALIGNN|crystal[- ]graph|graph networks?/i.test(head)) return 'news-graph';
    if (/\bgenerative\b|\bgenerat(?:e|es|ed|ing)\b|diffusion(?: models?| and| for| transformer)|inverse design|structure search|physics judge/i.test(head)) return 'news-search';
    if (/terahertz|picosecond|femtosecond|laser|light pulse|light[- ]induced|photo-?(?:galvanic|current|induced)|mid-infrared|^light\b|optical(?:ly)? (?:pump|driv)/i.test(head)) return 'news-light';
    var pressureText = head.replace(/\bambient[- ]pressure\b|\b(?:without|no)\s+(?:applied\s+|external\s+)?pressure\b|\bpressure[- ]free\b|\b(?:partial|vapou?r|gas)\s+pressures?\b/gi, '');
    if (/pressur(?:e|i[sz]ed|i[sz]ing)|diamond anvil|\bGPa\b|\bsqueez/i.test(pressureText)) return 'news-pressure';
    if (/\bs\s?±|\bs\+-|s[- ]plus[- ]minus|sign[- ](?:revers|chang)/i.test(head)) return 'news-multigap';
    if (/nanowire/i.test(head)) return 'news-topo';
    if (/kagome/i.test(head)) return 'news-kagome';
    if (/cuprate|CuO[₂2]|Zhang[– -]Rice/i.test(head)) return 'news-cuprate';
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
    if (/Josephson|Andreev|weak[- ]links?|\bjunctions?\b|co-?tunnel|three[- ]terminal|quantum dots?/i.test(head)) return 'news-junction';
    if (/\btwist(?:ed)?\b|twist[- ]angle|moir[eé]|magic[- ]angle/i.test(head)) return 'news-moire';
    if (/competi(?:tion|ng)|rivalry|coexist|tetracritic|multi-?component|phase transition between|two (?:superconducting |competing |quantum )?(?:states|orders|phases)|\bnematic\b|intertwined orders?/i.test(head)) return 'news-competition';
    if (/altermagnet|antiferromagnet|ferromagnet|magnetic order|magnetism|exchange[- ]coupled|odd[- ]parity magnets?|N[eé]el/i.test(head)) return 'news-magnetism';
    if (/proximit/i.test(head)) return 'news-proximity';
    if (/thermoelectric|thermal (?:transport|conductivity|Hall)|heat (?:transport|conduction|flow)|Nernst|Seebeck|thermali[sz]ation/i.test(head)) return 'news-thermal';
    if (/\bmonolayer\b(?!s)|atom(?:ically|ic)?[- ]thin|single[- ]layer|one[- ]atom[- ]thick/i.test(head)) return 'news-monolayer';
    if (/interfaces?|thin[- ]films?|\bfilms?\b|heterostructures?|epitax|substrates?|\bgrowth\b/i.test(head) || /[A-Z][a-z]?(?:[A-Z][a-z]?|\d)+\s?\/\s?[A-Z][a-z]?(?:[A-Z][a-z]?|\d)+/.test(head)) return 'news-interface';
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
    if (tp.indexOf('Electron–phonon') >= 0) return 'news-eph';
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
        if (parts.join('') !== token || parts.length < 2 || parts.some(function (part) { return symbols.indexOf(part.match(/^[A-Z][a-z]?/)[0]) < 0; })) return;
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

  const newsArticleFigure = function newsArticleFigure(item, kind) {
    var info = newsArticleDescribe(item);
    var art = kind || (item.ai_kind && typeof aiArticleArt === 'function' ? aiArticleArt(item) : newsArt(item));
    return h('div', { class: 'news-art', 'data-article-key': info.key, 'data-source-url': info.url,
      title: info.title }, miniCanvas(art, item));
  };
