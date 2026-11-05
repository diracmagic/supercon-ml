'use strict';
// content: original initialization order; invoked synchronously by bootstrap.js.
const initializeSuperconContent = function initializeSuperconContent() {


  /* ---------- references (DOIs checked against Crossref) ---------- */
  REFS = {
    onnes1911: { t: 'H. Kamerlingh Onnes, Commun. Phys. Lab. Univ. Leiden 120b (1911)' },
    meissner1933: { t: 'W. Meissner & R. Ochsenfeld, Naturwissenschaften 21, 787 (1933)', d: '10.1007/BF01504252' },
    london1935: { t: 'F. London & H. London, Proc. R. Soc. Lond. A 149, 71 (1935)', d: '10.1098/rspa.1935.0048' },
    gl1950: { t: 'V. L. Ginzburg & L. D. Landau, Zh. Eksp. Teor. Fiz. 20, 1064 (1950)' },
    abrikosov1957: { t: 'A. A. Abrikosov, J. Phys. Chem. Solids 2, 199 (1957)', d: '10.1016/0022-3697(57)90083-5' },
    cooper1956: { t: 'L. N. Cooper, Phys. Rev. 104, 1189 (1956)', d: '10.1103/PhysRev.104.1189' },
    bcs1957: { t: 'J. Bardeen, L. N. Cooper & J. R. Schrieffer, Phys. Rev. 108, 1175 (1957)', d: '10.1103/PhysRev.108.1175' },
    eliashberg1960: { t: 'G. M. Eliashberg, Sov. Phys. JETP 11, 696 (1960)' },
    josephson1962: { t: 'B. D. Josephson, Phys. Lett. 1, 251 (1962)', d: '10.1016/0031-9163(62)91369-0' },
    mcmillan1968: { t: 'W. L. McMillan, Phys. Rev. 167, 331 (1968)', d: '10.1103/PhysRev.167.331' },
    allendynes1975: { t: 'P. B. Allen & R. C. Dynes, Phys. Rev. B 12, 905 (1975)', d: '10.1103/PhysRevB.12.905' },
    liu2017hydride: { t: 'H. Liu et al., PNAS 114, 6990–6995 (2017)', d: '10.1073/pnas.1704505114' },
    matthias1954: { t: 'B. T. Matthias et al., Phys. Rev. 95, 1435 (1954)', d: '10.1103/PhysRev.95.1435' },
    gavaler1973: { t: 'J. R. Gavaler, Appl. Phys. Lett. 23, 480 (1973)', d: '10.1063/1.1654966' },
    steglich1979: { t: 'F. Steglich et al., Phys. Rev. Lett. 43, 1892 (1979)', d: '10.1103/PhysRevLett.43.1892' },
    bednorz1986: { t: 'J. G. Bednorz & K. A. Müller, Z. Phys. B 64, 189 (1986)', d: '10.1007/BF01303701' },
    wu1987: { t: 'M. K. Wu et al., Phys. Rev. Lett. 58, 908 (1987)', d: '10.1103/PhysRevLett.58.908' },
    anderson1987: { t: 'P. W. Anderson, Science 235, 1196 (1987)', d: '10.1126/science.235.4793.1196' },
    maeda1988: { t: 'H. Maeda et al., Jpn. J. Appl. Phys. 27, L209 (1988)', d: '10.1143/JJAP.27.L209' },
    parkin1988: { t: 'S. S. P. Parkin et al., Phys. Rev. Lett. 60, 2539 (1988)', d: '10.1103/PhysRevLett.60.2539' },
    schilling1993: { t: 'A. Schilling et al., Nature 363, 56 (1993)', d: '10.1038/363056a0' },
    gao1994: { t: 'L. Gao et al., Phys. Rev. B 50, 4260 (1994)', d: '10.1103/PhysRevB.50.4260' },
    maeno1994: { t: 'Y. Maeno et al., Nature 372, 532 (1994)', d: '10.1038/372532a0' },
    tsuei2000: { t: 'C. C. Tsuei & J. R. Kirtley, Rev. Mod. Phys. 72, 969 (2000)', d: '10.1103/RevModPhys.72.969' },
    nagamatsu2001: { t: 'J. Nagamatsu et al., Nature 410, 63 (2001)', d: '10.1038/35065039' },
    kitaev2001: { t: 'A. Yu. Kitaev, Phys.-Usp. 44, 131 (2001)', d: '10.1070/1063-7869/44/10S/S29' },
    kamihara2008: { t: 'Y. Kamihara et al., J. Am. Chem. Soc. 130, 3296 (2008)', d: '10.1021/ja800073m' },
    ren2008: { t: 'Z.-A. Ren et al., Chin. Phys. Lett. 25, 2215 (2008)', d: '10.1088/0256-307X/25/6/080' },
    hsu2008: { t: 'F.-C. Hsu et al., PNAS 105, 14262 (2008)', d: '10.1073/pnas.0807325105' },
    mazin2008: { t: 'I. I. Mazin et al., Phys. Rev. Lett. 101, 057003 (2008)', d: '10.1103/PhysRevLett.101.057003' },
    kuroki2008: { t: 'K. Kuroki et al., Phys. Rev. Lett. 101, 087004 (2008)', d: '10.1103/PhysRevLett.101.087004' },
    fukane2008: { t: 'L. Fu & C. L. Kane, Phys. Rev. Lett. 100, 096407 (2008)', d: '10.1103/PhysRevLett.100.096407' },
    bistritzer2011: { t: 'R. Bistritzer & A. H. MacDonald, PNAS 108, 12233 (2011)', d: '10.1073/pnas.1108174108' },
    scalapino2012: { t: 'D. J. Scalapino, Rev. Mod. Phys. 84, 1383 (2012)', d: '10.1103/RevModPhys.84.1383' },
    drozdov2015: { t: 'A. P. Drozdov et al., Nature 525, 73 (2015)', d: '10.1038/nature14964' },
    cao2018: { t: 'Y. Cao et al., Nature 556, 43 (2018)', d: '10.1038/nature26160' },
    drozdov2019: { t: 'A. P. Drozdov et al., Nature 569, 528 (2019)', d: '10.1038/s41586-019-1201-8' },
    somayazulu2019: { t: 'M. Somayazulu et al., Phys. Rev. Lett. 122, 027001 (2019)', d: '10.1103/PhysRevLett.122.027001' },
    li2019: { t: 'D. Li et al., Nature 572, 624 (2019)', d: '10.1038/s41586-019-1496-5' },
    ran2019: { t: 'S. Ran et al., Science 365, 684 (2019)', d: '10.1126/science.aav8645' },
    ortiz2020: { t: 'B. R. Ortiz et al., Phys. Rev. Lett. 125, 247002 (2020)', d: '10.1103/PhysRevLett.125.247002' },
    sun2023: { t: 'H. Sun et al., Nature 621, 493 (2023)', d: '10.1038/s41586-023-06408-7' },
    ko2025: { t: 'E. K. Ko et al., Nature 638, 935 (2025)', d: '10.1038/s41586-024-08525-3' },
    zhou2025: { t: 'G. Zhou et al., Nature 640, 641 (2025)', d: '10.1038/s41586-025-08755-z' },
    zhou2026: { t: 'G. Zhou et al., Natl. Sci. Rev. 13, nwag151 (2026)', d: '10.1093/nsr/nwag151' },
    song2025: { t: 'Y. Song et al., arXiv:2510.01273 (2025), preprint', u: 'https://arxiv.org/abs/2510.01273' },
    deng2026: { t: 'L. Deng et al., PNAS 123, e2536178123 (2026)', d: '10.1073/pnas.2536178123' },
    baroni2001: { t: 'S. Baroni et al., Rev. Mod. Phys. 73, 515 (2001)', d: '10.1103/RevModPhys.73.515' },
    giustino2017: { t: 'F. Giustino, Rev. Mod. Phys. 89, 015003 (2017)', d: '10.1103/RevModPhys.89.015003' },
    friedman2001: { t: 'J. H. Friedman, Ann. Stat. 29, 1189 (2001)', d: '10.1214/aos/1013203451' },
    sklearn2011: { t: 'F. Pedregosa et al., J. Mach. Learn. Res. 12, 2825 (2011)', u: 'https://jmlr.org/papers/v12/pedregosa11a.html' },
    mace2022: { t: 'I. Batatia et al., MACE, NeurIPS 35 (2022)', u: 'https://arxiv.org/abs/2206.07697' },
    macemp2023: { t: 'I. Batatia et al., A foundation model for atomistic materials chemistry, arXiv:2401.00096', u: 'https://arxiv.org/abs/2401.00096' },
    chgnet2023: { t: 'B. Deng et al., Nat. Mach. Intell. 5, 1031 (2023)', d: '10.1038/s42256-023-00716-3' },
    alignn2021: { t: 'K. Choudhary & B. DeCost, npj Comput. Mater. 7, 185 (2021)', d: '10.1038/s41524-021-00650-1' },
    xie2018: { t: 'T. Xie & J. C. Grossman, Phys. Rev. Lett. 120, 145301 (2018)', d: '10.1103/PhysRevLett.120.145301' },
    kaplan2025: { t: 'D. Kaplan et al., Eur. Phys. J. Plus 140, 58 (2025)', d: '10.1140/epjp/s13360-024-05947-w' },
    lesser2025: { t: 'O. Lesser et al., arXiv:2510.07373 (2025), preprint', u: 'https://arxiv.org/abs/2510.07373' },
    verbitsky2026: { t: 'L. Verbitsky et al., Chem. Mater. 38, 9080 (2026)', d: '10.1021/acs.chemmater.6c01826' },
    gashmard2026: { t: 'H. Gashmard, H. Shakeripour & M. Alaei, Sci. Rep. (2026)', d: '10.1038/s41598-026-76977-w' },
    nepal2026: { t: 'N. K. Nepal & L.-L. Wang, npj Comput. Mater. 12, 152 (2026)', d: '10.1038/s41524-026-01962-w' },
    itani2025: { t: 'S. Itani et al., arXiv:2512.10847 (2025), preprint', u: 'https://arxiv.org/abs/2512.10847' },
    prakash2026: { t: 'P. Prakash et al., npj Comput. Mater. 12, 286 (2026)', d: '10.1038/s41524-026-02117-7' },
    cordero2008: { t: 'B. Cordero et al., Dalton Trans. 2832 (2008)', d: '10.1039/b801115j' },
    vovk2005: { t: 'V. Vovk, A. Gammerman & G. Shafer, Algorithmic Learning in a Random World (Springer, 2005)', d: '10.1007/b106715' },
    gneiting2007: { t: 'T. Gneiting & A. E. Raftery, J. Am. Stat. Assoc. 102, 359 (2007)', d: '10.1198/016214506000001437' },
    jarvis2022: { t: 'K. Choudhary & K. Garrity, npj Comput. Mater. 8, 244 (2022)', d: '10.1038/s41524-022-00933-1' },
    alexandria2024: { t: 'T. F. T. Cerqueira et al., Adv. Mater. 36, 2307085 (2024)', d: '10.1002/adma.202307085' },
    nas2017: { t: 'B. Zoph & Q. V. Le, Neural architecture search with reinforcement learning, ICLR (2017)', u: 'https://arxiv.org/abs/1611.01578' },
    sommer2023: { t: 'T. Sommer et al., 3DSC, a dataset of superconductors including crystal structures, Sci. Data 10, 816 (2023)', d: '10.1038/s41597-023-02721-y' },
    jain2013: { t: 'A. Jain et al., The Materials Project, APL Mater. 1, 011002 (2013)', d: '10.1063/1.4812323' },
    presland1991: { t: 'M. R. Presland et al., Physica C 176, 95 (1991)', d: '10.1016/0921-4534(91)90700-9' },
    cavignac2026: { t: 'T. Cavignac et al., J. Phys. Mater. 9, 025014 (2026)', d: '10.1088/2515-7639/ae6620' },
    khim2021: { t: 'S. Khim et al., Science 373, 1012 (2021)', d: '10.1126/science.abe7518' },
    rosa2022: { t: 'P. F. S. Rosa et al., Commun. Mater. 3, 33 (2022)', d: '10.1038/s43246-022-00254-2' },
    li2020: { t: 'Q. Li et al., Commun. Mater. 1, 16 (2020)', d: '10.1038/s43246-020-0018-1' },
    ortiz2021: { t: 'B. R. Ortiz et al., Phys. Rev. Materials 5, 034801 (2021)', d: '10.1103/PhysRevMaterials.5.034801' }
  };


  /* ---------- recent advances, Nobel Prizes (DOIs checked against Crossref, 30 Oct 2026) ---------- */
  [
    ['tanaka2025', 'M. Tanaka et al., Nature 638, 99 (2025)', '10.1038/s41586-024-08494-7'],
    ['banerjee2025', 'A. Banerjee et al., Nature 638, 93 (2025)', '10.1038/s41586-024-08444-3'],
    ['ge2024', 'J. Ge et al., Phys. Rev. X 14, 021025 (2024)', '10.1103/PhysRevX.14.021025'],
    ['zheng2026', 'Y. Zheng et al., Science 393, 80 (2026)', '10.1126/science.ads0189'],
    ['yao2025', 'R. Yao et al., Phys. Rev. Lett. 134, 183402 (2025)', '10.1103/PhysRevLett.134.183402'],
    ['li2024', 'X. Li et al., Nature 626, 288 (2024)', '10.1038/s41586-023-06964-y'],
    ['dolui2024', 'K. Dolui et al., Phys. Rev. Lett. 132, 166001 (2024)', '10.1103/PhysRevLett.132.166001'],
    ['du2025', 'F. Du et al., Nature 641, 619 (2025)', '10.1038/s41586-025-08895-2'],
    ['ghosh2024', 'S. Ghosh et al., Nat. Mater. 23, 612 (2024)', '10.1038/s41563-024-01804-4'],
    ['xu2024', 'H. Xu et al., Science 384, eadh7691 (2024)', '10.1126/science.adh7691'],
    ['bourgund2025', 'D. Bourgund et al., Nature 637, 57 (2025)', '10.1038/s41586-024-08270-7'],
    ['shen2026', 'J. Shen et al., Science 392, 1396 (2026)', '10.1126/science.adw8329'],
    ['sakakibara2024', 'H. Sakakibara et al., Phys. Rev. Lett. 132, 106002 (2024)', '10.1103/PhysRevLett.132.106002'],
    ['msft2025', 'Microsoft Azure Quantum et al., Nature 638, 651 (2025)', '10.1038/s41586-024-08445-2'],
    ['vanloo2026', 'N. van Loo et al., Nature 650, 334 (2026)', '10.1038/s41586-025-09927-7'],
    ['xia2025', 'Y. Xia et al., Nature 637, 833 (2025)', '10.1038/s41586-024-08116-2'],
    ['guo2025', 'Y. Guo et al., Nature 637, 839 (2025)', '10.1038/s41586-024-08381-1'],
    ['han2025', 'T. Han et al., Nature 643, 654 (2025)', '10.1038/s41586-025-09169-7'],
    ['boulant2024', 'N. Boulant et al., Nat. Methods 21, 2013 (2024)', '10.1038/s41592-024-02472-7'],
    ['ballarino2025', 'A. Ballarino et al., Sci. Rep. 15, 20428 (2025)', '10.1038/s41598-025-08543-9'],
    ['yuan2025', 'J. Yuan et al., Phys. Rev. Lett. 135, 166002 (2025)', '10.1103/b5h4-ppdf'],
    ['hartwig2024', 'Z. S. Hartwig et al., IEEE Trans. Appl. Supercond. 34(2), 1 (2024)', '10.1109/TASC.2023.3332613'],
    ['fava2024', 'S. Fava et al., Nature 632, 75 (2024)', '10.1038/s41586-024-07635-2'],
    ['horio2025', 'M. Horio et al., Phys. Rev. Lett. 135, 046501 (2025)', '10.1103/p4c3-t34b'],
    ['wen2025', 'C. Wen et al., npj Quantum Mater. 10, 20 (2025)', '10.1038/s41535-025-00735-w'],
    ['kong2025', 'L. Kong et al., Nature 640, 55 (2025)', '10.1038/s41586-025-08703-x'],
    ['hanw2025', 'M. Han et al., Adv. Mater. 37, e13265 (2025)', '10.1002/adma.202513265'],
    ['bhattacharyya2024', 'P. Bhattacharyya et al., Nature 627, 73 (2024)', '10.1038/s41586-024-07026-7'],
    ['wang2024', 'N. Wang et al., Nature 634, 579 (2024)', '10.1038/s41586-024-07996-8'],
    ['lu2024', 'C. Lu et al., Phys. Rev. Lett. 132, 146002 (2024)', '10.1103/PhysRevLett.132.146002'],
    ['theuss2024', 'F. Theuss et al., Nat. Phys. 20, 1124 (2024)', '10.1038/s41567-024-02493-1'],
    ['maeno2024', 'Y. Maeno et al., Nat. Phys. 20, 1712 (2024)', '10.1038/s41567-024-02656-0'],
    ['ogata2023', 'S. Ogata et al., Phys. Rev. Lett. 130, 166001 (2023)', '10.1103/PhysRevLett.130.166001'],
    ['shi2026', 'T. Shi et al., Nat. Phys. 22, 1479 (2026)', '10.1038/s41567-026-03392-3'],
    ['merchant2023', 'A. Merchant et al., Nature 624, 80 (2023)', '10.1038/s41586-023-06735-9'],
    ['zhu2023', 'S. Zhu et al., Matter 6, 4401 (2023)', '10.1016/j.matt.2023.11.001'],
    ['retraction2023', 'Retraction note: N. Dasenbrock-Gammon et al., Nature 624, 460 (2023)', '10.1038/s41586-023-06774-2'],
    ['matthias1955', 'B. T. Matthias, Phys. Rev. 97, 74 (1955)', '10.1103/PhysRev.97.74'],
    ['zeni2025', 'C. Zeni et al., Nature 639, 624 (2025)', '10.1038/s41586-025-08628-5'],
    ['pogue2023', 'E. A. Pogue et al., npj Comput. Mater. 9, 181 (2023)', '10.1038/s41524-023-01131-3'],
    ['anderson1973', 'P. W. Anderson, Mater. Res. Bull. 8, 153 (1973)', '10.1016/0025-5408(73)90167-0'],
    ['chao1977', 'K. A. Chao, J. Spałek & A. M. Oleś, J. Phys. C 10, L271 (1977)', '10.1088/0022-3719/10/10/002'],
    ['alexandrov1981b', 'A. Alexandrov & J. Ranninger, Phys. Rev. B 24, 1164 (1981)', '10.1103/PhysRevB.24.1164'],
    ['hubbard1963', 'J. Hubbard, Proc. R. Soc. Lond. A 276, 238 (1963)', '10.1098/rspa.1963.0204'],
    ['baskaran1987', 'G. Baskaran, Z. Zou & P. W. Anderson, Solid State Commun. 63, 973 (1987)', '10.1016/0038-1098(87)90642-9'],
    ['kotliar1988', 'G. Kotliar & J. Liu, Phys. Rev. B 38, 5142 (1988)', '10.1103/PhysRevB.38.5142'],
    ['lee2006', 'P. A. Lee, N. Nagaosa & X.-G. Wen, Rev. Mod. Phys. 78, 17 (2006)', '10.1103/RevModPhys.78.17'],
    ['qin2020', 'M. Qin et al., Phys. Rev. X 10, 031016 (2020)', '10.1103/PhysRevX.10.031016'],
    ['emery1987', 'V. J. Emery, Phys. Rev. Lett. 58, 2794 (1987)', '10.1103/PhysRevLett.58.2794'],
    ['zhangrice1988', 'F. C. Zhang & T. M. Rice, Phys. Rev. B 37, 3759 (1988)', '10.1103/PhysRevB.37.3759'],
    ['scalapino1986', 'D. J. Scalapino, E. Loh & J. E. Hirsch, Phys. Rev. B 34, 8190 (1986)', '10.1103/PhysRevB.34.8190'],
    ['miyake1986', 'K. Miyake, S. Schmitt-Rink & C. M. Varma, Phys. Rev. B 34, 6554 (1986)', '10.1103/PhysRevB.34.6554'],
    ['monthoux1991', 'P. Monthoux, A. V. Balatsky & D. Pines, Phys. Rev. Lett. 67, 3448 (1991)', '10.1103/PhysRevLett.67.3448'],
    ['zaanen1989', 'J. Zaanen & O. Gunnarsson, Phys. Rev. B 40, 7391 (1989)', '10.1103/PhysRevB.40.7391'],
    ['tranquada1995', 'J. M. Tranquada et al., Nature 375, 561 (1995)', '10.1038/375561a0'],
    ['fradkin2015', 'E. Fradkin, S. A. Kivelson & J. M. Tranquada, Rev. Mod. Phys. 87, 457 (2015)', '10.1103/RevModPhys.87.457'],
    ['uemura1989', 'Y. J. Uemura et al., Phys. Rev. Lett. 62, 2317 (1989)', '10.1103/PhysRevLett.62.2317'],
    ['emery1995', 'V. J. Emery & S. A. Kivelson, Nature 374, 434 (1995)', '10.1038/374434a0'],
    ['wang2006', 'Y. Wang, L. Li & N. P. Ong, Phys. Rev. B 73, 024510 (2006)', '10.1103/PhysRevB.73.024510'],
    ['keimer2015', 'B. Keimer et al., Nature 518, 179 (2015)', '10.1038/nature14165'],
    ['alexandrov1981', 'A. Alexandrov & J. Ranninger, Phys. Rev. B 23, 1796 (1981)', '10.1103/PhysRevB.23.1796'],
    ['zhang2023', 'C. Zhang et al., Phys. Rev. X 13, 011010 (2023)', '10.1103/PhysRevX.13.011010'],
    ['varma1989', 'C. M. Varma et al., Phys. Rev. Lett. 63, 1996 (1989)', '10.1103/PhysRevLett.63.1996'],
    ['legros2019', 'A. Legros et al., Nat. Phys. 15, 142 (2019)', '10.1038/s41567-018-0334-2'],
    ['chen2023', 'L. Chen et al., Science 382, 907 (2023)', '10.1126/science.abq6100']
  ].forEach(function (r) { REFS[r[0]] = { t: r[1], d: r[2] }; });

  REFS.kagomeml2025 = { t: 'R. Albu Mustaf et al., Phys. Rev. Research 8, 023308 (2026)', d: '10.1103/lpqj-7hyg' };

  REFS.beenet2025 = { t: 'J. B. Gibson et al., npj Comput. Mater. 12, 95 (2026)', d: '10.1038/s41524-026-01964-8' };

  REFS.alignn2026 = { t: 'ALIGNN 2.0, arXiv:2609.19487 (2026), preprint', u: 'https://arxiv.org/abs/2609.19487' };

  REFS.periodic2025 = { t: 'TechCrunch, 30 Sep 2025; periodic.com', u: 'https://techcrunch.com/2025/09/30/former-openai-and-deepmind-researchers-raise-whopping-300m-seed-to-automate-science' };

  REFS.storm2026 = { t: 'Hello Super, github.com/diracmagic/supercon-ml (2026)', u: 'https://github.com/diracmagic/supercon-ml' };

  REFS.nobel2025 = { t: 'The Nobel Prize in Physics 2025, NobelPrize.org', u: 'https://www.nobelprize.org/prizes/physics/2025/summary/' };

  /* ---------- classic superconductors on the Tc chart (DOIs checked against Crossref, 5 Nov 2026) ---------- */
  [
    ['hardy1953', 'G. F. Hardy & J. K. Hulm, Phys. Rev. 89, 884 (1953)', '10.1103/PhysRev.89.884'],
    ['schooley1964', 'J. F. Schooley, W. R. Hosler & M. L. Cohen, Phys. Rev. Lett. 12, 474 (1964)', '10.1103/PhysRevLett.12.474'],
    ['chevrel1971', 'R. Chevrel, M. Sergent & J. Prigent, J. Solid State Chem. 3, 515 (1971)', '10.1016/0022-4596(71)90095-8'],
    ['matthias1972', 'B. T. Matthias et al., Science 175, 1465 (1972)', '10.1126/science.175.4029.1465'],
    ['sleight1975', 'A. W. Sleight, J. L. Gillson & P. E. Bierstedt, Solid State Commun. 17, 27 (1975)', '10.1016/0038-1098(75)90327-0'],
    ['jerome1980', 'D. Jérome et al., J. Phys. Lett. 41, L95 (1980)', '10.1051/jphyslet:0198000410409500'],
    ['ott1983', 'H. R. Ott et al., Phys. Rev. Lett. 50, 1595 (1983)', '10.1103/PhysRevLett.50.1595'],
    ['stewart1984', 'G. R. Stewart et al., Phys. Rev. Lett. 52, 679 (1984)', '10.1103/PhysRevLett.52.679'],
    ['cava1988', 'R. J. Cava et al., Nature 332, 814 (1988)', '10.1038/332814a0'],
    ['urayama1988', 'H. Urayama et al., Chem. Lett. 17, 55 (1988)', '10.1246/cl.1988.55'],
    ['tokura1989', 'Y. Tokura, H. Takagi & S. Uchida, Nature 337, 345 (1989)', '10.1038/337345a0'],
    ['hebard1991', 'A. F. Hebard et al., Nature 350, 600 (1991)', '10.1038/350600a0'],
    ['tanigaki1991', 'K. Tanigaki et al., Nature 352, 222 (1991)', '10.1038/352222a0'],
    ['saxena2000', 'S. S. Saxena et al., Nature 406, 587 (2000)', '10.1038/35020500'],
    ['petrovic2001', 'C. Petrovic et al., J. Phys.: Condens. Matter 13, L337 (2001)', '10.1088/0953-8984/13/17/103'],
    ['sarrao2002', 'J. L. Sarrao et al., Nature 420, 297 (2002)', '10.1038/nature01212'],
    ['ekimov2004', 'E. A. Ekimov et al., Nature 428, 542 (2004)', '10.1038/nature02449'],
    ['weller2005', 'T. E. Weller et al., Nat. Phys. 1, 39 (2005)', '10.1038/nphys0010'],
    ['emery2005', 'N. Emery et al., Phys. Rev. Lett. 95, 087003 (2005)', '10.1103/PhysRevLett.95.087003'],
    ['rotter2008', 'M. Rotter, M. Tegel & D. Johrendt, Phys. Rev. Lett. 101, 107006 (2008)', '10.1103/PhysRevLett.101.107006'],
    ['wang2012', 'Q.-Y. Wang et al., Chin. Phys. Lett. 29, 037402 (2012)', '10.1088/0256-307X/29/3/037402'],
    ['ma2022', 'L. Ma et al., Phys. Rev. Lett. 128, 167001 (2022)', '10.1103/PhysRevLett.128.167001']
  ].forEach(function (r) { REFS[r[0]] = { t: r[1], d: r[2] }; });


  // One entry per result. cards: the Theory & materials cards (by animation kind) it belongs to; 'field' = field-wide.
  RECENT = [
    { d: '2026-10', k: 'computation', cards: ['ai'], ref: 'storm2026', h: 'Storm 1.0: an AI agent designs a better Tc model',
      x: 'In this project an AI agent (Claude) proposed nine model designs; the winner, Storm 1.0, adds eleven physics features and deeper trees and cuts the cross-validated error against DFT-computed Tc from 1.05 K to 0.97 K, better in all five folds.' },
    { d: '2026-09', k: 'computation', cards: ['ai'], ref: 'alignn2026', h: 'ALIGNN 2.0 brings superconductor screening into a unified graph network',
      x: 'A line-graph neural-network framework for screening, force fields and inverse design reports a Tc error of about 0.86 K against DFT-computed Tc for electron–phonon superconductors from the structure alone, on its own test split, so the number is not directly comparable with Storm’s (preprint).' },
    { d: '2025-12', k: 'experiment', cards: ['ai'], ref: 'kagomeml2025', h: 'Machine learning points to two new kagome superconductors',
      x: 'Machine-learning screening flagged the kagome borides YRu₃B₂ and LuRu₃B₂, and measurements then found bulk superconductivity in both, at 0.81 K and 0.95 K, confirmed by magnetization, specific heat and transport.' },
    { d: '2025-09', k: 'news', cards: ['ai'], ref: 'periodic2025', h: 'Periodic Labs launches to build AI scientists',
      x: 'A start-up founded by former OpenAI and Google researchers came out of stealth with a $300 million seed round to pair AI models with autonomous labs; finding superconductors that work at higher temperatures is one of its stated goals.' },
    { d: '2025-03', k: 'computation', cards: ['ai', 'eliashberg'], ref: 'beenet2025', h: 'An AI workflow for finding conventional superconductors',
      x: 'BEE-NET, a deep network that predicts the electron–phonon spectral function α²F(ω) and Tc from structure, is combined with screening and first-principles checks into a complete discovery workflow; two of its predictions, Be₂HfNb₂ and Be₂Hf₂Nb, were then made and found to superconduct.' },
    { d: '2025-01', k: 'computation', cards: ['ai'], ref: 'zeni2025', h: 'MatterGen generates new inorganic materials on request',
      x: 'A diffusion model generates stable crystal structures with requested chemistry and properties; one generated compound was made, and its measured property came close to the target.' },
    { d: '2023-10', k: 'experiment', cards: ['ai'], ref: 'pogue2023', h: 'A closed machine-learning loop finds a new superconductor',
      x: 'Feeding each round of laboratory measurements back into a Tc model, the team found a previously unreported superconductor in the Zr–In–Ni system and re-discovered known superconductors missing from the training data.' },
    { d: '2026-07', k: 'experiment', cards: ['gl'], ref: 'zheng2026', h: 'Vortices split into fractional vortices',
      x: 'Scanning tunnelling microscopy on KFe₂As₂ showed single flux-quantum vortices splitting into two or three fractional cores, a hallmark of several coexisting condensates. The fractional vortices often line up in chains, which calculations identify as a new topological defect, the chiral skyrmion.' },
    { d: '2026-07', k: 'experiment', cards: ['heavy'], ref: 'shi2026', h: 'Pressure makes a van der Waals heavy-fermion metal superconduct',
      x: 'Suppressing the magnetic order of layered CeSiI under pressure gives a superconducting dome up to about 0.24 K, with signs of quantum-critical, probably unconventional pairing.' },
    { d: '2026-06', k: 'experiment', cards: ['spm', 'nickelate'], ref: 'shen2026', h: 'A nodeless gap in ambient-pressure nickelate films',
      x: 'Photoemission on superconducting (La,Pr,Sm)₃Ni₂O₇ films found a gap of about 18 meV along the zone diagonal, where a d-wave gap would vanish, and a finite gap everywhere else, so no nodes. That argues against cuprate-like d-wave pairing and is consistent with the s± state many theories favour, though photoemission cannot see the sign of the gap.' },
    { d: '2026-03', k: 'experiment', cards: ['hg1223'], ref: 'deng2026', h: 'A pressure quench keeps 151 K at ambient pressure',
      x: 'Squeezing Hg-1223 and releasing the pressure quickly at low temperature kept a metastable state with a 151 K onset, above the 133 K ambient-pressure record that stood since 1993.' },
    { d: '2026-03', k: 'experiment', cards: ['nickelate'], ref: 'zhou2026', h: 'Nickelate films pass 60 K at ambient pressure',
      x: 'Compressively strained bilayer nickelate films reached a superconducting onset above 60 K without applied pressure, with zero resistance up to 37 K.' },
    { d: '2026-02', k: 'experiment', cards: ['topo'], ref: 'vanloo2026', h: 'Parity read out in a two-site Kitaev chain',
      x: 'QuTech read the shared parity of a minimal Kitaev chain of two quantum dots in a single shot. This “poor man’s” Majorana pair is not topologically protected, and scaling it up is still open.' },
    { d: '2025-10', k: 'experiment', cards: ['josephson'], ref: 'nobel2025', h: 'Nobel Prize for macroscopic quantum tunnelling in Josephson circuits',
      x: 'John Clarke, Michel Devoret and John Martinis showed in 1984–85 that a superconducting circuit with a Josephson junction tunnels as a whole and has quantised energy levels, the basis of today’s superconducting qubits.' },
    { d: '2025-10', k: 'experiment', cards: ['mgb2'], ref: 'yuan2025', h: 'Terahertz pulses drive the Higgs and Leggett modes of MgB₂',
      x: 'Tuned terahertz pulses excited an amplitude (Higgs) mode of MgB₂’s π-band gap and a damped oscillation assigned to the Leggett mode, where the two gaps’ phases swing against each other. The assignments are still debated.' },
    { d: '2025-10', k: 'experiment', cards: ['hydride'], ref: 'song2025', h: 'Possible superconductivity near room temperature in LaSc₂H₂₄',
      x: 'A preprint reports onsets of 271–298 K at 195–266 GPa in a ternary hydride. It has not been peer reviewed yet.' },
    { d: '2025-07', k: 'experiment', cards: ['mgb2'], ref: 'ballarino2025', h: 'An MgB₂ line carries 94 kA for the High-Luminosity LHC',
      x: 'CERN’s cold-powering link uses MgB₂ cables from 4.5 K to about 20 K and REBCO leads above that. Designed for 117 kA, it carried 94 kA, the limit of the test supplies.' },
    { d: '2025-07', k: 'experiment', cards: ['hg1223'], ref: 'horio2025', h: 'Hg-1223’s outer CuO₂ planes pair far more strongly than Bi-2223’s',
      x: 'Micro-focused photoemission resolved the inner and outer planes of trilayer (Hg,Re)-1223 separately. The outer-plane gap, about 57 meV, is much larger than in lower-Tc Bi-2223 (about 43 meV), while the inner planes of the two are similar (about 60 meV); the authors argue that this stronger outer-plane pairing is key to the record Tc.' },
    { d: '2025-05', k: 'experiment', cards: ['bcs'], ref: 'yao2025', h: 'Fermion pairs photographed atom by atom',
      x: 'A quantum gas microscope imaged individual lithium-6 atoms in a strongly interacting two-dimensional Fermi gas and saw opposite-spin atoms bound into extended pairs across the BCS–BEC crossover.' },
    { d: '2025-05', k: 'experiment', cards: ['moire'], ref: 'han2025', h: 'Signs of chiral superconductivity in rhombohedral graphene',
      x: 'In four- and five-layer rhombohedral graphene, whose bands are flat near their edges even without a moiré pattern, superconductivity grows out of a spin- and valley-polarised metal and shows magnetic hysteresis, consistent with broken time-reversal symmetry.' },
    { d: '2025-04', k: 'experiment', cards: ['eliashberg', 'hydride'], ref: 'du2025', h: 'Tunnelling measures the gap of H₃S',
      x: 'Planar tunnelling at about 160 GPa found a fully open s-wave gap, 2Δ ≈ 60 meV, that shrinks to about 44 meV in D₃S: the isotope shift expected for phonon-mediated pairing.' },
    { d: '2025-03', k: 'experiment', cards: ['iron'], ref: 'kong2025', h: 'A gap that varies with the lattice in FeTeSe flakes',
      x: 'Scanning tunnelling microscopy on thin FeTe₀.₅₅Se₀.₄₅ found the gap varying by more than 30% with the lattice period, a “pair density modulation” traced to different gaps on the two iron sublattices.' },
    { d: '2025-02', k: 'experiment', cards: ['magic'], ref: 'tanaka2025', h: 'Magic-angle graphene’s superfluid is unexpectedly stiff',
      x: 'A superconducting microwave circuit measured the kinetic inductance of twisted bilayer graphene. The superfluid stiffness is far above what conventional theory allows, pointing to the quantum geometry of the flat bands.' },
    { d: '2025-02', k: 'experiment', cards: ['magic'], ref: 'banerjee2025', h: 'Trilayer graphene’s stiffness points to nodal pairing',
      x: 'Microwave measurements on twisted trilayer graphene found a superfluid stiffness that grows linearly as temperature falls, a sign of nodes in the gap, and that scales with Tc across doping, as in the cuprates.' },
    { d: '2025-02', k: 'experiment', cards: ['topo'], ref: 'msft2025', h: 'Single-shot parity readout in InAs–Al nanowires',
      x: 'Microsoft read the fermion parity of nanowire devices in one shot with about 1% error. The authors say this alone does not prove Majorana modes, and the protocol used to qualify the devices is disputed.' },
    { d: '2025-02', k: 'experiment', cards: ['nickelate'], ref: 'zhou2025', h: 'Nickelate films superconduct above 40 K without pressure',
      x: 'Compressively strained (La,Pr)₃Ni₂O₇ films showed a superconducting onset above 40 K at ambient pressure, following signatures in La₃Ni₂O₇ films (Ko et al., 2024).' },
    { d: '2025-01', k: 'experiment', cards: ['stripes', 'mott'], ref: 'bourgund2025', h: 'Cold atoms show the first fragments of charge stripes',
      x: 'In a mixed-dimensional Fermi–Hubbard simulator, dopant holes attracted each other through the spin background, and the authors report the first signatures of individual stripes, precursors of the stripes predicted for cuprate models.' },
    { d: '2024-11', k: 'theory', cards: ['triplet'], ref: 'maeno2024', h: 'Sr₂RuO₄ after thirty years',
      x: 'A Perspective reviews how the textbook spin-triplet candidate now looks singlet-like, and lists the conflicting experiments that a final answer must reconcile.' },
    { d: '2024-10', k: 'experiment', cards: ['moire'], ref: 'xia2025', h: 'Superconductivity in twisted bilayer WSe₂',
      x: 'Two groups found superconductivity in twisted WSe₂ (Tc about 0.2–0.4 K; also Guo et al., 2025), so moiré flat-band superconductivity is not unique to graphene.' },
    { d: '2024-10', k: 'experiment', cards: ['magnet'], ref: 'boulant2024', h: 'An 11.7 T whole-body MRI images the human brain',
      x: 'The Iseult scanner, whose 132-tonne NbTi magnet runs in superfluid helium at about 1.8 K, produced in vivo brain images at 11.7 tesla, above the 10.5 T used before.' },
    { d: '2024-10', k: 'experiment', cards: ['nickelate'], ref: 'wang2024', h: 'Bulk superconductivity near 80 K in La₂PrNi₂O₇',
      x: 'Replacing some lanthanum with praseodymium gave a nearly pure bilayer nickelate that superconducts in bulk at 18–20 GPa, with an 82.5 K onset and zero resistance at 60 K.' },
    { d: '2024-07', k: 'experiment', cards: ['rebco', 'london'], ref: 'fava2024', h: 'Light makes YBCO expel magnetic field above Tc',
      x: 'Mid-infrared pulses on YBa₂Cu₃O₆.₄₈ expelled an applied field for about a picosecond at 100 K and above. The authors link it to light-enhanced superconducting correlations; what the state is remains open.' },
    { d: '2024-05', k: 'experiment', cards: ['gl', 'triplet'], ref: 'ge2024', h: 'Possible charge-4e and charge-6e superconductivity in a kagome metal',
      x: 'Rings of CsV₃Sb₅ showed the usual flux period h/2e at low temperature, giving way to h/4e and then h/6e as the temperature rises. The authors read this as evidence of charge-4e and charge-6e superconductivity in a fluctuating regime above the paired state; the interpretation is not settled.' },
    { d: '2024-05', k: 'computation', cards: ['dwave', 'mott', 'stripes'], ref: 'xu2024', h: 'Hubbard-model numerics find d-wave pairing with stripes',
      x: 'Two leading numerical methods agree that the 2D Hubbard model with next-nearest-neighbour hopping hosts d-wave superconductivity, coexisting with partially filled stripes when hole doped.' },
    { d: '2024-05', k: 'experiment', cards: ['triplet'], ref: 'theuss2024', h: 'Ultrasound favours single-component pairing in UTe₂',
      x: 'No jumps in the shear moduli at Tc point to a single-component, odd-parity order parameter, against the two-component chiral states proposed earlier.' },
    { d: '2024-04', k: 'computation', cards: ['eliashberg', 'hydride'], ref: 'dolui2024', h: 'Eliashberg screening predicts about 160 K in Mg₂IrH₆ at ambient pressure',
      x: 'A high-throughput Migdal–Eliashberg search flagged metastable Mg₂IrH₆ as a conventional superconductor near 160 K without pressure. It is still only a prediction.' },
    { d: '2024-04', k: 'theory', cards: ['nickelate'], ref: 'lu2024', h: 'Interlayer coupling could drive nickelate pairing',
      x: 'A bilayer t–J model shows strong interlayer coupling turning d-wave into interlayer s-wave pairing and raising Tc. Competing proposals are not yet settled by experiment.' },
    { d: '2024-03', k: 'theory', cards: ['spm'], ref: 'sakakibara2024', h: 'Theory predicts s± pairing in pressurised La₃Ni₂O₇',
      x: 'Fluctuation-exchange calculations give an s± state whose sign flips between the bonding and antibonding d(3z²−r²) bands, the sign-changing idea known from the iron pnictides.' },
    { d: '2024-03', k: 'experiment', cards: ['rebco'], ref: 'hartwig2024', h: 'A REBCO fusion magnet reaches 20 tesla',
      x: 'The SPARC toroidal-field model coil, wound from 270 km of REBCO tape and cooled to about 20 K, reached 20 T; a deliberate quench test is guiding fusion-magnet design.' },
    { d: '2024-02', k: 'experiment', cards: ['hydride', 'london'], ref: 'bhattacharyya2024', h: 'Quantum sensors image the Meissner effect in CeH₉',
      x: 'Nitrogen-vacancy centres built into a diamond anvil mapped field expulsion and trapped flux in cerium hydride at megabar pressure, direct local evidence of superconductivity, with patchy superconducting regions.' },
    { d: '2024-02', k: 'experiment', cards: ['bcs', 'phase'], ref: 'li2024', h: 'A pairing gap survives above the superfluid transition',
      x: 'Spectroscopy of a uniform, strongly interacting Fermi gas found a pairing gap above Tc. Simple BCS theory has pairs form and condense together, so this supports preformed pairs.' },
    { d: '2024-02', k: 'experiment', cards: ['josephson'], ref: 'ghosh2024', h: 'A Josephson diode that works up to 77 K',
      x: 'Stacked, twisted Bi₂Sr₂CaCu₂O₈₊δ flakes carry supercurrent more easily one way than the other up to liquid-nitrogen temperature; earlier Josephson diodes worked only near 4 K.' },
    { d: '2023-12', k: 'experiment', cards: ['field'], ref: 'zhu2023', h: 'LK-99’s jumps traced to Cu₂S impurities',
      x: 'The viral 2023 claim of room-temperature superconductivity in copper-doped lead apatite unravelled: the sharp features come from a structural transition of Cu₂S impurities, with no zero resistance.' },
    { d: '2023-11', k: 'experiment', cards: ['strange'], ref: 'chen2023', h: 'Shot noise suggests a strange metal has no quasiparticles',
      x: 'In nanowires of the heavy-fermion strange metal YbRh₂Si₂, current noise is strongly suppressed compared with ordinary metals, which Fermi-liquid scattering cannot explain. The current may not be carried by well-defined quasiparticles.' },
    { d: '2023-11', k: 'computation', cards: ['ai'], ref: 'merchant2023', h: 'Graph networks propose 2.2 million stable crystals',
      x: 'Google’s GNoME models predicted 2.2 million crystal structures stable against known phases. How many are both new and useful is still debated.' },
    { d: '2023-11', k: 'experiment', cards: ['field', 'hydride'], ref: 'retraction2023', h: 'The lutetium hydride room-temperature claim is retracted',
      x: 'Nature retracted the March 2023 report of near-ambient superconductivity in nitrogen-doped lutetium hydride after eight of its eleven authors said the paper did not accurately reflect where the samples came from, how they were measured or how the data were processed.' },
    { d: '2023-07', k: 'experiment', cards: ['field'], ref: 'sun2023', h: 'Superconductivity near 80 K in pressurised La₃Ni₂O₇',
      x: 'A bilayer nickelate showed signs of superconductivity near 80 K at about 14–44 GPa, opening the newest high-Tc family.' },
    { d: '2023-04', k: 'experiment', cards: ['heavy'], ref: 'ogata2023', h: 'NMR backs a parity switch in CeRh₂As₂',
      x: 'Knight-shift measurements show that both field-separated superconducting phases are spin-singlet. That supports a field-induced switch to odd parity in which the singlet gap changes sign between the two cerium layers of the unit cell, possible because each layer lacks inversion symmetry.' },
    { d: '2023-01', k: 'computation', cards: ['bipolaron'], ref: 'zhang2023', h: 'Light bipolarons could superconduct at high temperature',
      x: 'Quantum Monte Carlo simulations of electrons coupled to phonons that modulate their hopping between sites find small but light bipolarons, whose condensation temperature is high for phonon-driven pairing.' }
  ];


  NOBEL = [
    { y: 1913, anim: 'onnes', who: 'Heike Kamerlingh Onnes', what: 'Low-temperature physics and liquid helium, which let him discover superconductivity in mercury in 1911.' },
    { y: 1972, anim: 'bcs', who: 'John Bardeen, Leon N. Cooper, J. Robert Schrieffer', what: 'The BCS theory of superconductivity: Cooper pairs bound by lattice vibrations.' },
    { y: 1973, anim: 'josephson', who: 'Leo Esaki, Ivar Giaever; Brian D. Josephson', what: 'Electron tunnelling in semiconductors and superconductors (Esaki, Giaever), and the prediction of the Josephson effects (Josephson).' },
    { y: 1987, anim: 'cuprate', who: 'J. Georg Bednorz, K. Alexander Müller', what: 'The discovery of superconductivity in ceramic copper oxides, which started the high-Tc era.' },
    { y: 2003, anim: 'gl', who: 'Alexei A. Abrikosov, Vitaly L. Ginzburg, Anthony J. Leggett', what: 'Pioneering theory of superconductors and superfluids, including type II vortices and Ginzburg–Landau theory.' },
    { y: 2025, anim: 'mqt', who: 'John Clarke, Michel H. Devoret, John M. Martinis', what: 'Macroscopic quantum tunnelling and energy quantisation in a superconducting circuit with a Josephson junction, the basis of superconducting qubits.' }
  ];

  NOBEL_RELATED = [
    { y: 1962, anim: 'landau', who: 'Lev Landau', what: 'Theories of condensed matter, especially liquid helium; co-author of Ginzburg–Landau theory.' },
    { y: 1996, anim: 'he3', who: 'David M. Lee, Douglas D. Osheroff, Robert C. Richardson', what: 'Superfluid helium-3, a Cooper-paired superfluid with p-wave pairing.' },
    { y: 2013, anim: 'higgs', who: 'François Englert, Peter Higgs', what: 'The Higgs mechanism, whose condensed-matter version appears first in superconductors (Anderson, 1963).' },
    { y: 2016, anim: 'bkt', who: 'David J. Thouless, F. Duncan M. Haldane, J. Michael Kosterlitz', what: 'Topological phase transitions, including the vortex-driven transition of thin superconducting and superfluid films.' }
  ];

  MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  KIND_LABEL = { experiment: 'Experiment', theory: 'Theory', computation: 'Computation', news: 'News' };


  /* ---------- Live curated content ----------
     progress/content.json adds recent advances (with their references) or hides built-in ones, so new results
     reach the Theory & materials cards, the News & papers view and the AI view without an app release.
     Everything in it is treated as data: strings are length-limited and rendered as text, links must be https. */
  CONTENT_URL = 'https://raw.githubusercontent.com/' + REPO + '/' + BRANCH + '/progress/content.json';

  RECENT_BUILTIN = RECENT.slice();

  contentState = { at: 0, busy: false, applied: '', updated: '' };

  CONTENT_KINDS = { experiment: 1, theory: 1, computation: 1, news: 1 };

  // Superconductors whose discovery an AI or machine-learning model guided and that experiments then confirmed, newest first
  // (checked by hand against each paper; progress/content.json "found" replaces this list without an app update)
  AI_FOUND_BUILTIN = [
    { d: '2026', ref: 'kagomeml2025', h: 'YRu₃B₂ and LuRu₃B₂', tc: 'Tc 0.81 K and 0.95 K', m: 'ML screening, then DFT',
      x: 'Two kagome-lattice ruthenium borides. Machine learning pre-screened a large space of element combinations, first-principles calculations checked the most promising ones, and magnetization and specific heat confirmed bulk superconductivity.' },
    { d: '2026', ref: 'beenet2025', h: 'Be₂Hf₂Nb and Be₂HfNb₂', tc: 'Tc from 3.2 K and 4.2 K', m: 'Graph networks, then DFT',
      x: 'BEE-NET, an ensemble of graph networks that predicts the Eliashberg function, together with machine-learned potentials and DFT, narrowed 1.3 million candidate structures to 741 stable compounds with a computed Tc above 5 K. Two Hf-substituted relatives of the known superconductor Be₂Nb₃ were made: DFT predicted 9.3 K and 5.1 K, resistivity shows superconductivity from 3.2 K and 4.2 K, and specific heat shows that it is bulk in Be₂Hf₂Nb.' },
    { d: '2025', refs: ['lesser2025', 'verbitsky2026'], h: 'PtPb₃Bi, then AuPb₄₋ₓBiₓ, PdPb₄₋ₓBiₓ and RhPb₄₋ₓBiₓ', tc: 'Tc about 3 K; 4.9, 4.2 and 3.4 K', m: 'Gaussian process on local bonding',
      x: 'GP-Tc, a Gaussian-process model that reads local bonding (the spread of electron-affinity differences between neighbouring atoms, with bond lengths), predicted superconductivity in stoichiometric PtPb₃Bi, which was then made and superconducts near 3 K. A follow-up study of the same structure type made three new relatives; resistivity, magnetization and specific heat show bulk superconductivity at 4.9, 4.2 and 3.4 K.' },
    { d: '2025', ref: 'kaplan2025', h: 'Mo₂₀Re₆Si₄', tc: 'Tc 5.4 K', m: 'Deep learning on composition',
      x: 'Neural networks trained on SuperCon compositions, with chemical intuition about the Mo₂₀X₆Z₄ family, pointed to Mo–Re–Si; the new compound superconducts below 5.4 K in magnetization and specific heat. A second proposal, Mo₄Re₂Ge, showed no superconductivity above 1.8 K.' },
    { d: '2023', ref: 'pogue2023', h: 'A Zr–In–Ni phase near ZrNiIn₄', tc: 'Tc about 9 K', m: 'Closed loop with experiments',
      x: 'What the authors call the first closed-loop discovery: a machine-learning model proposed candidates, high-throughput synthesis and measurements tested them, and the results retrained the model, over four cycles. The superconducting phase is metastable and has not been isolated as a single phase. The loop also re-discovered five known superconductors that were missing from its training data.' }
  ];

  AI_FOUND = AI_FOUND_BUILTIN.slice();

  // AI predictions that, as far as we know, no experiment has tested yet; one moves to the list above once confirmed
  // (progress/content.json "watch" replaces this list without an app update)
  AI_WATCH_BUILTIN = [
    { d: '2026', ref: 'gashmard2026', h: '22 plutonium compounds, and hydrides', tc: 'predicted Tc above 50 K', m: 'Neural networks on composition',
      x: 'Convolutional and LSTM networks, trained with a new set of 53,196 non-superconductors, flagged ambient-pressure plutonium compounds from existing crystal databases, such as Pu₂Co₁₇ (about 89 K), and over 40 hydrides with predicted Tc up to 100 K.' },
    { d: '2026', ref: 'nepal2026', h: 'Ca₅B₃N₆, TaNbC₂, Nb₃B₃C, MoRuB₂ and others', tc: 'predicted Tc 15–35 K', m: 'ML-guided DFPT',
      x: 'Machine learning steered electron–phonon calculations over 417 boron, carbon and borocarbide compounds, including ones with unstable phonons. Candidates just above the convex hull include Ca₅B₃N₆ (35 K), TaNbC₂ (28.4 K), Nb₃B₃C (16.4 K) and MoRuB₂ (15.6 K).' },
    { d: '2025', ref: 'itani2025', h: 'Unreported materials in the GNoME database', tc: 'predicted Tc above 10 K', m: 'Fine-tuned language models',
      x: 'Open-source language models, fine-tuned on 78,203 literature records that an LLM workflow extracted, screened the GNoME database and flagged unreported materials with predicted Tc above 10 K; the authors stress that the candidates are unverified.' }
  ];

  AI_WATCH = AI_WATCH_BUILTIN.slice();

  // published work that cites supercon-ml, newest first (progress/content.json "cited_by"); the Cite view lists it
  CITED_BY = [];

  // the message form's delivery service (progress/content.json "contact"): a Web3Forms access key or a Formspree form id;
  // the inbox it delivers to is set up with the service and never appears in the app or the repository
  CONTACT = null;

  AI_FOUND_NOTE = { x: 'All of these superconduct below 10 K; as far as we know, no higher-Tc candidate proposed by an AI model has been confirmed yet. Making the predicted compound is often the hard part: in a 2026 diffusion-model study, most of the synthesized candidates did not form the predicted structure.', ref: 'prakash2026' };

  (function startContent() {
    try { var cached = store.get('content'); if (cached) applyContent(JSON.parse(cached)); } catch (e) { /* ignore a bad cache */ }
  })();

};
