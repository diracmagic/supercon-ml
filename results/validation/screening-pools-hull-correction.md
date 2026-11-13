# The screening pools of rounds 1 to 6 and the convex hull: a correction

Record of 2026-11-12. It says what was found about the pools of screening rounds 1 to 6, how it was checked, what
depends on it, and how the correction is published. Nothing in this file is a model result: every number here is a
count of database entries or a distance to a convex hull, except in section 6, which reports a screening that was run
on a branch and is not published.

## 1. In short

- Screening rounds 1 to 6 took their pools from one file, JARVIS-DFT 3D (`dft_3d`, as jarvis-tools 2026.6.12 serves
  it), and kept an entry only if the file's `ehull` field was at most 0.05 eV/atom. The published records and the app
  describe this as "within 50 meV/atom of the convex hull": `screen.pool.rule` and `screen.hurricane.pool.rule` in
  `progress/progress.json`, the pool steps in `results/screen_round1.json` to `screen_round4.json` and
  `screen_round6.json`, and the steps of Hurricane's background in `results/hurricane_round3.json`, `_round4`,
  `_round5` and `_round9`. Storm's caveat speaks of "a structure that DFT says is stable or nearly so".
- That field does not follow the convex hull of the file's own formation energies. It kept about a tenth of the file,
  and what it kept is not what lies near the hull: of the entries it passed, 36% lie more than 50 meV/atom above the
  hull computed from the file, and it left out 88% of the entries that lie within 50 meV/atom of that hull.
- Both published lists are affected. Of Storm's 102 candidates (screening round 5), 62 lie more than 50 meV/atom above
  the computed hull and 13 more than 200 meV/atom. Of the 42 candidates of Hurricane 9.0 (screening round 6), 10 lie
  more than 50 meV/atom above it, among them ranks 1, 2 and 5, and 7 more than 200 meV/atom. Section 3 lists every
  candidate.
- No list, rank or score is changed by this correction, and no released model reads the field as an input. The pools
  decide which compounds a model is asked about, not what it answers. Section 4 says what else was chosen with the
  field.
- The correction step (`python ml/pipeline.py screenhull`, module `ml/screen_hull.py`) computes each published
  candidate's distance to the hull of the file's formation energies and publishes it next to the lists
  (`screen.hull` in `progress/progress.json`); the app shows it for every candidate and says under both lists how they
  were selected. Both lists stand as published until a screening on a corrected pool replaces them.
- A first screening of Hurricane 9.0 on a corrected and wider pool was run on a branch. Its lists are not published;
  section 6 says why.

## 2. The `ehull` field of JARVIS-DFT 3D

All 93,902 entries of the file were read. The convex hull was computed from the file's own
`formation_energy_peratom`, with the elements at zero, for the 93,743 entries in the 32,577 chemical systems of up to
five elements (pymatgen's `PhaseDiagram`; `ml/jarvis_hull_check.py` on the branch `claude/pool-census`, run
43114917286, section 7).

| | The `ehull` field | Distance to the hull computed from the file |
| --- | ---: | ---: |
| Median, eV/atom | 1.72 | 0.0375 |
| Entries at most 0.05 eV/atom | 9,339 of 93,902 | 50,547 of 93,743 |
| Entries with an ICSD number at most 0.05 eV/atom | 2,241 of 20,812 (11%) | |

| Entries (93,743) | Field at most 0.05 | Field above 0.05 |
| --- | ---: | ---: |
| Computed distance at most 0.05 | 6,016 | 44,531 |
| Computed distance above 0.05 | 3,323 | 39,873 |

- The correlation between the two, on a seeded sample of 4,000 chemical systems, is 0.06 (Pearson).
- Against a second source: of the 33,527 compositions that the Materials Project (build 2025-09-25) puts within
  50 meV/atom of its own hull and that JARVIS-DFT also has, the field puts 3,668 within 50 meV/atom.
- Under the rules of Hurricane's pool (2 to 5 elements, at most 40 atoms in the cell, band gap at most 1 eV), the field
  passes 5,754 entries (4,638 compositions), of which 2,555 lie more than 50 meV/atom above the computed hull. The
  computed distance passes 35,275 entries (27,078 compositions). 10,361 compositions have an entry with an ICSD
  number, at any distance.
- Under the same size rules for metals (Storm's pool), the field passes 5,040 entries, of which 2,363 lie more than
  50 meV/atom above the computed hull; the computed distance passes 29,886.

What the field holds was not established. It is exactly zero for 6,325 entries; this record states only what was
measured in the copy of the file named above. The tracker of jarvis-tools has an open note of 2021 that the 3D dataset
holds `ehull` for far fewer entries than before ([usnistgov/jarvis, issue 160](https://github.com/usnistgov/jarvis/issues/160));
whether that is related was not established either.

## 3. The published candidates against the computed hull

Distances in eV/atom, from run 43114917286. "ICSD number" is the file's own link to an experimental structure. The
correction step (section 5) computes the same distances again from the file and publishes them with the lists.

### Hurricane 9.0, screening round 6 (42 candidates)

32 lie within 50 meV/atom of the computed hull, 10 beyond, 7 beyond 200 meV/atom; 10 have an ICSD number.

| Rank | Formula | JARVIS-DFT entry | ehull field | Distance to the computed hull | ICSD number |
| ---: | --- | --- | ---: | ---: | --- |
| 1 | Cu8O | JVASP-150511 | 0.0000 | 0.1014 | no |
| 2 | CaClO | JVASP-93832 | 0.0000 | 0.3298 | no |
| 3 | SmO | JVASP-19779 | 0.0000 | 0.0575 | yes |
| 4 | Yb2InSn | JVASP-37617 | 0.0000 | 0.0096 | no |
| 5 | SrMg3O | JVASP-186814 | 0.0000 | 0.7007 | no |
| 6 | Yb3Ce | JVASP-128322 | 0.0049 | 0.1907 | no |
| 7 | YbCuSn | JVASP-145804 | 0.0000 | 0.0000 | no |
| 8 | YbGa2 | JVASP-20420 | 0.0000 | 0.0000 | yes |
| 9 | PrO | JVASP-16493 | 0.0000 | 0.0184 | yes |
| 10 | YbIn5Rh | JVASP-16400 | 0.0000 | 0.0000 | yes |
| 11 | NdO | JVASP-49844 | 0.0000 | 0.0230 | no |
| 12 | YbIn5Co | JVASP-17895 | 0.0000 | 0.0000 | yes |
| 13 | YbIn | JVASP-129550 | 0.0173 | 0.0000 | no |
| 14 | BaClO | JVASP-113040 | 0.0000 | 0.2711 | no |
| 15 | Yb3Ga9Pd2 | JVASP-171094 | 0.0000 | 0.0000 | no |
| 16 | Yb3Ga9Pt2 | JVASP-118972 | 0.0000 | 0.0000 | no |
| 17 | Pr2Ga5Cu3 | JVASP-106012 | 0.0000 | 0.0000 | no |
| 18 | PrGa3 | JVASP-42026 | 0.0000 | 0.0000 | no |
| 19 | BaOF | JVASP-117591 | 0.0256 | 0.8382 | no |
| 20 | PrTl3 | JVASP-20286 | 0.0000 | 0.0000 | yes |
| 21 | YbGa3Cu | JVASP-109656 | 0.0000 | 0.0000 | no |
| 22 | PrCu5 | JVASP-8002 | 0.0496 | 0.0041 | yes |
| 23 | CeTl3 | JVASP-17773 | 0.0026 | 0.0000 | yes |
| 24 | PrIn2Cu9 | JVASP-120726 | 0.0000 | 0.0065 | no |
| 25 | SrClO | JVASP-110096 | 0.0000 | 0.3617 | no |
| 26 | SrOF2 | JVASP-118314 | 0.0402 | 0.9987 | no |
| 27 | PrGa5Ni | JVASP-162930 | 0.0245 | 0.0371 | no |
| 28 | CeGaCu4 | JVASP-101467 | 0.0000 | 0.0000 | no |
| 29 | LaCeCu12 | JVASP-140429 | 0.0000 | 0.0000 | no |
| 30 | CeCu5 | JVASP-19820 | 0.0000 | 0.0000 | yes |
| 31 | SrNiF2 | JVASP-134812 | 0.0000 | 1.1568 | no |
| 32 | YbIn4Pd | JVASP-152553 | 0.0000 | 0.0000 | no |
| 33 | YbIn4Pt | JVASP-151922 | 0.0000 | 0.0033 | no |
| 34 | Yb2In8Ir | JVASP-151620 | 0.0000 | 0.0000 | no |
| 35 | BaNiF4 | JVASP-151129 | 0.0000 | 0.0003 | no |
| 36 | Ce2Ga12Ni | JVASP-165420 | 0.0000 | 0.0000 | yes |
| 37 | YbGa4Ni | JVASP-152176 | 0.0000 | 0.0002 | no |
| 38 | YbIn4Ni | JVASP-152253 | 0.0000 | 0.0000 | no |
| 39 | U2Zn17 | JVASP-154877 | 0.0000 | 0.0000 | no |
| 40 | Pr2Zn17 | JVASP-154784 | 0.0023 | 0.0000 | no |
| 41 | CeUZn17 | JVASP-140457 | 0.0000 | 0.0196 | no |
| 42 | Ce2Zn17 | JVASP-155091 | 0.0000 | 0.0000 | no |

### Storm, screening round 5 (102 candidates)

40 lie within 50 meV/atom of the computed hull, 62 beyond, 13 beyond 200 meV/atom; 7 have an ICSD number; the median
distance is 0.078 eV/atom.

| Rank | Formula | JARVIS-DFT entry | ehull field | Distance to the computed hull | ICSD number |
| ---: | --- | --- | ---: | ---: | --- |
| 1 | InGa3 | JVASP-104848 | 0.0000 | 0.0428 | no |
| 2 | In2SnPb | JVASP-101186 | 0.0000 | 0.0142 | no |
| 3 | InGa2Sn2 | JVASP-155738 | 0.0000 | 0.0633 | no |
| 4 | Ga3Bi | JVASP-37780 | 0.0000 | 0.0897 | no |
| 5 | ZnGa3 | JVASP-39538 | 0.0000 | 0.0623 | no |
| 6 | Zn2InGa2 | JVASP-155749 | 0.0000 | 0.0379 | no |
| 7 | TlIn2Ga2 | JVASP-155756 | 0.0000 | 0.0325 | no |
| 8 | TlGa2Ge2 | JVASP-155743 | 0.0357 | 0.0934 | no |
| 9 | SnHgPb | JVASP-160802 | 0.0000 | 0.1958 | no |
| 10 | TlGa2Sn2 | JVASP-155736 | 0.0000 | 0.0371 | no |
| 11 | CdGa2Sn2 | JVASP-156096 | 0.0000 | 0.1142 | no |
| 12 | SnHgBi | JVASP-158496 | 0.0000 | 0.2059 | no |
| 13 | CdBiPb | JVASP-161079 | 0.0000 | 0.1293 | no |
| 14 | GaSnHg | JVASP-161010 | 0.0000 | 0.1925 | no |
| 15 | BeTlGa4 | JVASP-65134 | 0.0000 | 0.4265 | no |
| 16 | TlZn2Ga2 | JVASP-155733 | 0.0000 | 0.0459 | no |
| 17 | Tl3Ga | JVASP-102993 | 0.0000 | 0.0721 | no |
| 18 | ZnGa | JVASP-130243 | 0.0000 | 0.0684 | no |
| 19 | Cd2InSn2 | JVASP-156103 | 0.0000 | 0.0831 | no |
| 20 | BeInGa4 | JVASP-65235 | 0.0000 | 0.4085 | no |
| 21 | Tl3Ge | JVASP-107227 | 0.0000 | 0.1361 | no |
| 22 | HgBiPb | JVASP-156414 | 0.0000 | 0.1833 | no |
| 23 | InGaBi | JVASP-160993 | 0.0194 | 0.0869 | no |
| 24 | TlCdBi | JVASP-161081 | 0.0000 | 0.1017 | no |
| 25 | TlInSn | JVASP-160803 | 0.0000 | 0.0764 | no |
| 26 | BeZn2Bi | JVASP-71116 | 0.0000 | 0.3929 | no |
| 27 | LiLaZn2 | JVASP-156920 | 0.0000 | 0.0436 | no |
| 28 | CdGaBi | JVASP-161004 | 0.0000 | 0.1046 | no |
| 29 | TlZn2Sn2 | JVASP-155744 | 0.0000 | 0.0600 | no |
| 30 | BaSrGa4 | JVASP-110282 | 0.0000 | 0.0000 | no |
| 31 | Ba4BeZn | JVASP-64216 | 0.0003 | 0.9110 | no |
| 32 | InGaPb | JVASP-160989 | 0.0000 | 0.0909 | no |
| 33 | TlZn2In2 | JVASP-155761 | 0.0000 | 0.0631 | no |
| 34 | SrGa4 | JVASP-20206 | 0.0000 | 0.0000 | yes |
| 35 | MgGa5 | JVASP-168087 | 0.0000 | 0.0574 | no |
| 36 | Tl3Zn | JVASP-110876 | 0.0000 | 0.1179 | no |
| 37 | TlGaPb | JVASP-160990 | 0.0000 | 0.1219 | no |
| 38 | TlHgSb | JVASP-155993 | 0.0000 | 0.1945 | no |
| 39 | BaGa4 | JVASP-14661 | 0.0000 | 0.0000 | yes |
| 40 | LiSnHg2 | JVASP-80996 | 0.0000 | 0.1652 | no |
| 41 | Ba4BeCd | JVASP-64779 | 0.0000 | 0.8599 | no |
| 42 | CaGa3 | JVASP-122651 | 0.0340 | 0.1112 | no |
| 43 | BeTlIn4 | JVASP-65245 | 0.0000 | 0.4900 | no |
| 44 | CaGa4 | JVASP-14561 | 0.0000 | 0.0000 | yes |
| 45 | LiZn2Ge2 | JVASP-158170 | 0.0000 | 0.0834 | no |
| 46 | BaHg2Pb2 | JVASP-156056 | 0.0395 | 0.1146 | no |
| 47 | Tl6S | JVASP-50057 | 0.0000 | 0.0956 | no |
| 48 | MgBeGa4 | JVASP-64894 | 0.0000 | 0.4197 | no |
| 49 | LiInHg2 | JVASP-77465 | 0.0000 | 0.0844 | no |
| 50 | LiGaHg2 | JVASP-81846 | 0.0000 | 0.3684 | no |
| 51 | BaLi2Zn2 | JVASP-158256 | 0.0000 | 0.0680 | no |
| 52 | SrGa3 | JVASP-122712 | 0.0273 | 0.0978 | no |
| 53 | ZnIn3 | JVASP-78991 | 0.0000 | 0.0792 | no |
| 54 | SrLi2Zn2 | JVASP-155635 | 0.0000 | 0.0355 | no |
| 55 | SrTl3 | JVASP-107977 | 0.0000 | 0.0000 | no |
| 56 | BaLaGa4 | JVASP-179118 | 0.0000 | 0.1358 | no |
| 57 | LiLaHg2 | JVASP-79828 | 0.0000 | 0.0000 | no |
| 58 | Al2Zn2In | JVASP-155765 | 0.0000 | 0.0383 | no |
| 59 | Sr2AlGa3 | JVASP-108075 | 0.0000 | 0.0000 | no |
| 60 | NaLi2Zn | JVASP-161412 | 0.0000 | 0.1110 | no |
| 61 | La2ZnHg | JVASP-100191 | 0.0335 | 0.0317 | no |
| 62 | KBeGa4 | JVASP-74563 | 0.0000 | 0.4740 | no |
| 63 | Zn3Ge | JVASP-78995 | 0.0000 | 0.1397 | no |
| 64 | LiCaGa2 | JVASP-186125 | 0.0000 | 0.0828 | no |
| 65 | KBaTl2 | JVASP-69171 | 0.0000 | 0.0604 | no |
| 66 | BaNaTl2 | JVASP-100952 | 0.0000 | 0.0072 | no |
| 67 | CaZn2Ge2 | JVASP-17274 | 0.0000 | 0.0148 | yes |
| 68 | Li2CdBi | JVASP-169699 | 0.0000 | 0.0000 | no |
| 69 | CaLaZn2 | JVASP-40873 | 0.0000 | 0.0000 | no |
| 70 | SrZn2Ge2 | JVASP-15791 | 0.0000 | 0.0000 | yes |
| 71 | KTl2Bi | JVASP-40047 | 0.0000 | 0.0000 | no |
| 72 | SrLaZn2 | JVASP-156876 | 0.0000 | 0.0189 | no |
| 73 | SrHg2Pb | JVASP-111300 | 0.0000 | 0.0000 | no |
| 74 | Ba2LiGa | JVASP-64087 | 0.0000 | 0.0384 | no |
| 75 | MgZnAs | JVASP-75632 | 0.0000 | 0.3253 | no |
| 76 | MgScGa4 | JVASP-186511 | 0.0000 | 0.1470 | no |
| 77 | Ba2LiTl | JVASP-179584 | 0.0000 | 0.0000 | no |
| 78 | NaGa4 | JVASP-14728 | 0.0000 | 0.0000 | yes |
| 79 | CaHgPb | JVASP-8455 | 0.0000 | 0.1476 | yes |
| 80 | BaSrTl2 | JVASP-105723 | 0.0000 | 0.0159 | no |
| 81 | SrInHg2 | JVASP-40282 | 0.0000 | 0.0108 | no |
| 82 | NaTl2Sb | JVASP-79064 | 0.0000 | 0.0293 | no |
| 83 | Ca2ZnGa3 | JVASP-103512 | 0.0000 | 0.0011 | no |
| 84 | NaTl2Sn | JVASP-106568 | 0.0000 | 0.0000 | no |
| 85 | GaAgSn | JVASP-160998 | 0.0000 | 0.1084 | no |
| 86 | Li2ZnPb | JVASP-110109 | 0.0000 | 0.0199 | no |
| 87 | SrTlHg2 | JVASP-37625 | 0.0000 | 0.0104 | no |
| 88 | BaTl2In | JVASP-158786 | 0.0000 | 0.0444 | no |
| 89 | Ba2MgTl | JVASP-109020 | 0.0000 | 0.0000 | no |
| 90 | NaLaTl2 | JVASP-79928 | 0.0000 | 0.0000 | no |
| 91 | CdSnPd | JVASP-182811 | 0.0046 | 0.1868 | no |
| 92 | Ca2GaGe | JVASP-181335 | 0.0000 | 0.0947 | no |
| 93 | BaIn2Pb | JVASP-179129 | 0.0000 | 0.0840 | no |
| 94 | Li2ZnSn | JVASP-173037 | 0.0000 | 0.0138 | no |
| 95 | LiMgSn | JVASP-179507 | 0.0000 | 0.1201 | no |
| 96 | NaSrTl2 | JVASP-181129 | 0.0000 | 0.1139 | no |
| 97 | LiCdGa | JVASP-182791 | 0.0000 | 0.0815 | no |
| 98 | BaAl2Zn2 | JVASP-158083 | 0.0000 | 0.0174 | no |
| 99 | LiCdGe | JVASP-156340 | 0.0000 | 0.0940 | no |
| 100 | LiTl3 | JVASP-105793 | 0.0000 | 0.0540 | no |
| 101 | BaMg6B | JVASP-92900 | 0.0000 | 0.3663 | no |
| 102 | Mg6CdB | JVASP-92923 | 0.0000 | 0.3484 | no |

## 4. What was chosen with the field, and what was not

- The pools of screening rounds 1 to 6, Storm's and Hurricane's (`ml/screen.py`, `storm_pool` and `hurricane_pool`): an
  entry stayed only if the field was at most 0.05 eV/atom.
- The entry that stands for a composition of which the file holds several (`one_per_composition`): the one with the
  lowest field, described as the most stable.
- The compounds with no superconductivity record that the classifiers of Hurricane 3.0, 4.0 and 9.0 learned from at a
  low weight as probable non-superconductors, and on which their false alarms were counted: they are Hurricane's pool
  (`hurricane3.background`), so they are the compounds the field passed, not the compounds near the hull: of the 3,881
  compounds of Hurricane 9.0's background, 1,803 lie more than 50 meV/atom above the computed hull (run 43123563097,
  section 7). The models are kept as they were released, and the share of false alarms of Hurricane 9.0 (1 of the 591
  compounds that Radar sent it) stands for that set of compounds.
- The JARVIS-DFT entry that stood for a 3DSC compound in the check that a chance does not move when a structure comes
  from JARVIS-DFT instead of the Materials Project (`hurricane3.matched`, Hurricane's rounds 3 to 5): again the entry
  with the lowest field.
- One input of Hurricane's round 5, which led to no release: for the compounds of the pool, "the distance above the
  convex hull" was the field (`ml/hurricane5.py`), while the training compounds carried the Materials Project's
  distance.
- Not chosen with the field: the computed and measured data that Storm, Radar and Hurricane learn from (the
  background above apart), their features, and their tests on those data (folds, the locked test set, time windows).
  Storm, Radar and Hurricane 9.0 do not read the field.

## 5. How the correction is computed and published

`ml/screen_hull.py` reads the file through `screen.load_rows`, as the screening rounds did, and stops unless it is the
file of this record: the SHA-256 of one line per row (identifier, formation energy, band gap, atoms in the cell, ICSD
link) must be 465925380733c02fe03da2c76adeda63d352649881dfcc2184cddfa4428c7761, the value that four runs of 11 and 12
November 2026 printed for the 93,902 rows (section 7). For every entry with a formation energy it solves one linear
programme: the lowest energy that a mixture of the entries of the same chemical system and its subsystems can have at
the entry's composition, with the elements at zero and each composition at its lowest energy; the distance is the
entry's formation energy minus that, not below zero. Every published candidate and a seeded sample of 300 other
entries are then compared with pymatgen's phase diagram, and the step stops if any distance differs by more than
0.0001 eV/atom.

The step writes `results/screen_hull_correction.json` (the counts over the file, the check, one row per candidate)
and adds one field to the screen block of `progress/progress.json`, `screen.hull`, with each candidate's distance in
eV/atom rounded to four decimals, and one entry to the activity log. It runs no model. What it may change is recorded
in `results/validation/screen-hull-correction-publication.json`, and `tests/test_screen_publication.py` checks that
taking the field out again gives the screen block as it was published, hash for hash.

## 6. A first screening on a corrected, wider pool (screening round 7): run on a branch, not published

After the finding, Hurricane's pool was built again from four open sources: JARVIS-DFT with the hull distance computed
as in section 5, the Materials Project (build 2025-09-25, only the entries it marks CC BY), the Alexandria PBE convex
hull (release 2025.07.02, CC BY 4.0) and the Crystallography Open Database (public domain). GNoME (CC BY-NC 4.0) was
counted and not used. The protocol was declared before the run (branch `claude/screen-round7`, commit
fbca16df163893cde4f1add76d22e11834b5feff, `results/validation/hurricane9-screen7-declaration-v1.md`; protocol SHA-256
46c955b68e68a52a291eba5398757125a22fbcd44f4a47db08c330d0f1eecfd2).

The run ([43358591536](https://github.com/diracmagic/supercon-ml/actions/runs/43358591536), commit
993dd5a9b609b3607933825305af0f6c7520ffaf, record SHA-256
2359b1a596d2588a485a6f124e5caec43f190242de7252a204d7c579ea6fc603) reproduced the released computation of Hurricane 9.0
as its protocol requires and screened 118,750 compounds with no superconductivity record: 34,553 with an experimental
structure in one of the sources and 84,197 known from calculation only. Radar sent 38,090 of them to Hurricane, which
answered "not known" for 28,634 and judged 9,456.

Its two lists are not published. Hurricane 9.0 gave 1,956 of the 9,456 compounds it judged (21%) a chance of at least
one half; in the pool of round 6 it was 1 of 54. All 100 listed compounds are copper oxides, with chances from 0.59 to
0.998 and a T<sub>c</sub> if superconducting of 39 to 100 K. They are of two kinds.

- Substituted variants of known cuprate superconductors. The lists leave out a compound whose composition, or whose
  exact set of elements, a known superconductor has; a measured composition with one more element passes. Rank 1 of
  the list with experimental structures is Ba<sub>1.888</sub>Na<sub>0.094</sub>YCu<sub>3</sub>Cl<sub>0.057</sub>O<sub>6.961</sub>
  (COD 1526964), a substituted YBa<sub>2</sub>Cu<sub>3</sub>O<sub>7</sub>, and 12 of its 50 compounds lie, in
  Hurricane's own measure of distance, within 0.3 of a superconducting training compound.
- Copper oxides that are not layered cuprates, such as YCu<sub>3</sub>Se<sub>2</sub>ClO<sub>8</sub>, copper arsenates
  and tellurates, and hypothetical compounds like them in the list from calculation only. Hurricane 9.0 reads the
  composition only and gives them a cuprate's chance and T<sub>c</sub>. The band-gap rule does not remove them: without
  a Hubbard U on copper, as in JARVIS-DFT and the Materials Project, many insulating copper(II) compounds come out
  metallic.

This is what the test of Hurricane 9.0 had measured: among the compositions of parent compounds first reported after
its training data end, it gave at least an even chance to 39% of those measured not to superconduct. The 0.17% of
false alarms of its release was counted on the 591 compounds that Radar sent it from the pool of round 6, of which it
judged 54. A wider pool does not change what the model can tell apart, so Hurricane's list of round 6 stays as
published, with the computed distances, until a later round replaces it under rules declared before its run. The
lists, the counts and the pool of the run on the branch are in its log and its artifact.

## 7. Runs

Count-only runs on the branch `claude/pool-census`; each printed its report in the job log between markers, and the
SHA-256 of the report was checked against the one printed with it.

| What | Run | Commit | Report SHA-256 |
| --- | --- | --- | --- |
| Pool census, run 4: Hurricane-like counts, the Materials Project build, GNoME counted | [43109139887](https://github.com/diracmagic/supercon-ml/actions/runs/43109139887) | 544343e0fb18fea65796de52597dd84a348189f2 | 3afe7fbef4eebc414d2a8d936e580181e8a034d2bd6b7e46545667ecea26c0c2 |
| Pool census, run 5: two tracks, the databases' hulls compared | [43111774877](https://github.com/diracmagic/supercon-ml/actions/runs/43111774877) | bd5faa31699ca5ce5cbf1ae855663861584ce23b | 592d6ac5548bfc1a2899b1e43c8da3ca65398afe3a5b8b57bfa50fe279cb846f |
| COD access probe | [43112938822](https://github.com/diracmagic/supercon-ml/actions/runs/43112938822) | 6a9575d82a64269f4e9279e9d398df9e5587478b | checked in the job log |
| JARVIS-DFT hull check, a sample of 4,000 chemical systems | [43114277650](https://github.com/diracmagic/supercon-ml/actions/runs/43114277650) | d863dd9b649aa420e834306b657933c1c01b5a18 | 445d35baee88860b6083f54a32eecdb678c83345b41ec895371a4c095b5df68c |
| JARVIS-DFT hull check, every chemical system and the published candidates | [43114917286](https://github.com/diracmagic/supercon-ml/actions/runs/43114917286) | e61c48ee1d88d2d02d43f05ace7086e419b15282 | fc9373c1f2a47cd882bd789e6e53180d06c0728c21c8c7c1ac9b0a46e55996d0 |

The digest of the file's rows was printed by the count-only runs [43123563097](https://github.com/diracmagic/supercon-ml/actions/runs/43123563097), [43125373652](https://github.com/diracmagic/supercon-ml/actions/runs/43125373652) and [43126793006](https://github.com/diracmagic/supercon-ml/actions/runs/43126793006) and by run 43358591536 (section 6), all on the
branch `claude/screen-round7`; each also computed the distance of all 93,902 entries by the linear programme of section 5
(50,656 within 50 meV/atom) and compared 300 of them with pymatgen (largest difference 0.0 eV/atom).

## 8. What follows from this

- Storm's list still stands as screening round 5 published it, from a pool selected with the field. It needs a
  screening on a corrected pool; until then the app says so under the list and shows each candidate's computed
  distance.
- Hurricane's list still stands as screening round 6 published it, with the same note and distances. Section 6 says
  why the first attempt to replace it is not published.
- The released models are kept as they are (section 4).
- The published result files named in section 1 are kept as they were written and are not rewritten; this record and
  `screen.hull` are the correction to what they say about the hull.
- What the `ehull` field of the file holds was not established; this record states only what was measured in the copy
  of the file named in section 2.
