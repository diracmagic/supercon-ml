# The screening pool: what rounds 1 to 6 read, and what round 7 reads

Record of 2026-11-12. It says what was found about the pool of the earlier screening rounds, how it was checked, which
open sources a wider pool can read and under which licences, and what the count-only runs showed before the rules of
screening round 7 were frozen. Nothing in this file is a model result: every number here is a count of database
entries or a distance to a convex hull.

## 1. In short

- Screening rounds 1 to 6 took their pool from one file, JARVIS-DFT 3D (`dft_3d`, as jarvis-tools 2026.6.12 serves
  it), and kept an entry only if the file's `ehull` field was at most 0.05 eV/atom. The README and the app described
  this as "within 50 meV/atom of the convex hull".
- That field does not follow the convex hull of the file's own formation energies. It kept about a tenth of the file,
  and what it kept is not what lies near the hull: of the entries it passed, 36% lie more than 50 meV/atom above the
  hull computed from the file, and it left out 88% of the entries that lie within 50 meV/atom of that hull.
- Published lists are affected. Of Storm's 102 candidates, 62 lie more than 50 meV/atom above the computed hull and 13
  more than 200 meV/atom. Of the 42 candidates of Hurricane 9.0 (screening round 6), 10 lie more than 50 meV/atom
  above it, among them ranks 1, 2 and 5, and 7 more than 200 meV/atom. Section 3 lists every candidate.
- No model changes because of this. The pools decide which compounds a model is asked about, not what it answers.
  One thing does depend on the old pool: Hurricane 9.0 learned, at a low weight, from compounds of that pool as
  probable non-superconductors, and that released model is kept as it is.
- Screening round 7 builds Hurricane's pool again from four open sources and computes the JARVIS-DFT hull distance
  itself (`ml/hurricane9_screen7.py`, `results/validation/hurricane9-screen7-declaration-v1.md`). Storm's list is not
  re-screened by that round and still stands as round 5 published it; it needs a screening of its own.

## 2. The `ehull` field of JARVIS-DFT 3D

All 93,902 entries of the file were read. The convex hull was computed from the file's own
`formation_energy_peratom`, with the elements at zero, for the 93,743 entries in the 32,577 chemical systems of up to
five elements (pymatgen's `PhaseDiagram`; `ml/jarvis_hull_check.py` on the branch `claude/pool-census`, run
43114917286, section 5).

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
measured in the copy of the file named above.

## 3. The published candidates against the computed hull

Distances in eV/atom, from run 43114917286. "ICSD number" is the file's own link to an experimental structure.

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
distance is 0.078 eV/atom. Storm's list is not screened again by screening round 7. That round publishes these
distances with its record (`screen.hurricane.hull.storm` in `progress/progress.json`), computed again from the file, and
the app shows them next to each candidate.

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

## 4. Open sources for a wider pool, and their licences

Read without an account or a key. The licence decides what a list built on a source may be published under: the
results of this repository are under CC BY 4.0 (`LICENSE-results.md`).

| Source | What was read | Licence | In screening round 7 |
| --- | --- | --- | --- |
| [JARVIS-DFT](https://jarvis.nist.gov/) 3D (`dft_3d`, as jarvis-tools 2026.6.12 serves it) | 93,902 entries: formation energy, OptB88vdW band gap, ICSD link, structure | [NIST open licence](https://www.nist.gov/open/license) | yes, with the hull distance computed in the run |
| [Materials Project](https://materialsproject.org/), build 2025-09-25, summary collection in the AWS Open Data bucket `materialsproject-build` | 210,579 documents in 21 files (409 MB); 164,969 marked BY-C, 45,610 marked BY-NC (derived from GNoME), 10,090 deprecated | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) for the entries marked BY-C | yes: the 154,879 current entries marked BY-C; the others are not read |
| [Alexandria](https://alexandria.icams.rub.de/) PBE convex hull, release 2025.07.02 (`convex_hull.json.bz2`) | 174,601 entries (168 MB) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | yes |
| [Crystallography Open Database](https://www.crystallography.net/cod/), its own table through its public read-only database | 535,218 entries when probed (newest 2026-11-10); 61,145 with 2 to 6 elements and no hydrogen in the formula | public domain | yes: the usable rows, read once and stored in `results/screen_round7_cod.csv.gz` |
| GNoME stable materials (Google DeepMind) | 554,054 rows | [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) | no: counted only |
| OQMD, AFLOW | not read | not confirmed for this use | no |
| ICSD, MPDS | not read | subscription | no |

- The Materials Project marks each entry with its licence (`builder_meta.license`); the entries marked BY-NC come from
  GNoME and carry its non-commercial licence, so they are left out without being read. Of the entries used, 49,283
  are marked as not theoretical and have an ICSD number, 103,260 are theoretical without one, and 2,336 are theoretical
  with one; round 7 takes "theoretical is false" as an experimental structure.
- The COD's formulas are the compositions refined in each entry, partly occupied sites included (for example
  `Ba2 Cu1.16 Hg0.84 O4.19`). Its interface for small queries answers; a large export through it was cut by the
  server, so the rows are read from its public read-only database (host `www.crystallography.net`, user
  `cod_reader`, no password). Of its 535,218 entries, 1,020 are marked theoretical, 151 retracted and 5,433 duplicates.
- GNoME: 462,636 compositions pass Hurricane's earlier size rules with a band gap of at most 1 eV or none, 447,267 of
  them in neither track of pool census run 5 (section 5). A list built on them would have to carry the non-commercial licence;
  whether to publish one is a separate decision, and round 7 does not.

## 5. The census runs

Count-only runs on the branch `claude/pool-census`; each printed its report in the job log between markers, and the
SHA-256 of the report was checked against the one printed with it.

| What | Run | Commit | Report SHA-256 |
| --- | --- | --- | --- |
| Pool census, run 4: Hurricane-like counts, the Materials Project build, GNoME counted | [43109139887](https://github.com/diracmagic/supercon-ml/actions/runs/43109139887) | 544343e0fb18fea65796de52597dd84a348189f2 | 3afe7fbef4eebc414d2a8d936e580181e8a034d2bd6b7e46545667ecea26c0c2 |
| Pool census, run 5: two tracks, the databases' hulls compared | [43111774877](https://github.com/diracmagic/supercon-ml/actions/runs/43111774877) | bd5faa31699ca5ce5cbf1ae855663861584ce23b | 592d6ac5548bfc1a2899b1e43c8da3ca65398afe3a5b8b57bfa50fe279cb846f |
| COD access probe | [43112938822](https://github.com/diracmagic/supercon-ml/actions/runs/43112938822) | 6a9575d82a64269f4e9279e9d398df9e5587478b | checked in the job log |
| JARVIS-DFT hull check, a sample of 4,000 chemical systems | [43114277650](https://github.com/diracmagic/supercon-ml/actions/runs/43114277650) | d863dd9b649aa420e834306b657933c1c01b5a18 | 445d35baee88860b6083f54a32eecdb678c83345b41ec895371a4c095b5df68c |
| JARVIS-DFT hull check, every chemical system and the published candidates | [43114917286](https://github.com/diracmagic/supercon-ml/actions/runs/43114917286) | e61c48ee1d88d2d02d43f05ace7086e419b15282 | fc9373c1f2a47cd882bd789e6e53180d06c0728c21c8c7c1ac9b0a46e55996d0 |

## 6. The count-only runs of screening round 7

`python ml/hurricane9_screen7.py --counts` on the branch `claude/screen-round7` (workflow
`.github/workflows/screen7-counts.yml`): the pool from the real sources, with no Radar, no model and no list, and
nothing written. The rules of the pool were changed between the runs because of what the counts and the named
compounds showed. No model output was seen at any point.

| Run | Commit | Report SHA-256 | Pool | Experimental track | Calculation only |
| --- | --- | --- | ---: | ---: | ---: |
| [43120175352](https://github.com/diracmagic/supercon-ml/actions/runs/43120175352) | 50a6fa829efe389c716e2da78bfe504f98642ba2 | 6419262c3e3acd6116e66211284dd88f28d61e57dc71a9b880463244a2b7f067 | 121,859 | 37,482 | 84,377 |
| [43123563097](https://github.com/diracmagic/supercon-ml/actions/runs/43123563097) | 1f9f47ad5a79bab9b2ea25a5eaf708514a60fc4c | dcdaedeeb75a0cd8bb619fcb496d783874803fa87cb47b5fe868a126aeb4178a | 119,628 | 35,497 | 84,131 |
| [43125373652](https://github.com/diracmagic/supercon-ml/actions/runs/43125373652) | ff0133d58d17723de31a6329d4656e276cc8a763 | 91494ab944cf1fd286fb00c7de97f539e2dc3b04281b73f8b196e4719f253801 | 118,757 | 34,560 | 84,197 |
| [43126793006](https://github.com/diracmagic/supercon-ml/actions/runs/43126793006) | 6b39eac96a61485311f9d458d3ae3734da906bf9 | 6498e0a62b91c3fc278cabf194b6b2b6f169be19b4fa9f379fc4595c215a945b | 118,750 | 34,553 | 84,197 |

- After run 1. A composition stayed in the pool if any calculated entry of it had a band gap of at most 1 eV, so a
  hypothetical metallic structure brought in compounds that are insulators as they were made (the sample showed
  K<sub>2</sub>SO<sub>4</sub>, COD 1000049). Since then one calculated entry speaks for each composition: one marked
  experimental before any other, then one near its source's hull, then by source; its gap and hull distance decide.
- After run 2. The run checks 64 well-known compounds by name. Every one of 18 wide-gap insulators among them (NaCl,
  MgO, Al<sub>2</sub>O<sub>3</sub>, CaF<sub>2</sub> and BaSO<sub>4</sub> among them) was left out, and the 14 that stayed
  have a calculated gap of at most 1 eV: correlated compounds such as Sr<sub>2</sub>IrO<sub>4</sub>,
  CaRuO<sub>3</sub>, LaMnO<sub>3</sub> and RuCl<sub>3</sub>, and ZnO, an insulator whose OptB88vdW gap in JARVIS-DFT
  (0.97 eV) lies far below the measured one. The other 32 were left out as known: a SuperCon, 3DSC or datasheet record, a
  computed T<sub>c</sub>, or exactly the elements of a known superconductor. The run also showed entries
  marked experimental far above their source's hull, for instance the Materials Project's CdB<sub>2</sub> (mp-1072852,
  2.57 eV/atom). The experimental structure named with a compound is now one of exactly its composition where there
  is one, and the JARVIS-DFT rows are bound by the hash this run printed.
- After run 3. The run listed the entries marked experimental more than 0.5 eV/atom above their source's hull: 462 in
  JARVIS-DFT and 1,972 in the Materials Project. The sample it printed (the 12 furthest and every 40th after them) is
  made up mostly of molecular, coordination and hydrated compounds and nitrogen-rich compounds, and it includes
  entries that are plainly faulty, such as elemental Ta at 5.15 eV/atom, elemental Ir at 3.78 and an
  SrRuO<sub>3</sub> at 4.16. Since then a calculated entry more than 0.5 eV/atom above its source's hull is not used at
  all, neither its mark nor its gap: 11,970 entries of JARVIS-DFT and 11,620 of the Materials Project.
- Run 4 is the pool of the frozen protocol (`results/validation/hurricane9-screen7-declaration-v1.md`).

The pool of run 4, by source and track:

| Source that stands for the compound | Experimental track | Calculation only |
| --- | ---: | ---: |
| JARVIS-DFT | 7,819 | 8,095 |
| Materials Project | 12,548 | 4,954 |
| Alexandria | 734 | 71,148 |
| COD (a measured composition that no calculated entry has) | 13,452 | 0 |
| Total | 34,553 | 84,197 |

- Left out as known: 5,906 with a SuperCon or 3DSC record, 6,501 made of exactly the elements of a known
  superconductor, 3,637 with a computed T<sub>c</sub>, 165 whose composition the datasheet lists, 31 reported or
  predicted by others.
- 11,141 compounds of the experimental track are COD compositions with no calculated entry of the same material, so no
  calculated band gap: 5,156 oxides, 1,586 sulfides, selenides or tellurides, 1,042 halides other than fluorides, 811
  fluorides, 802 borides, carbides, silicides or germanides, 647 pnictides and 1,097 intermetallics. Some are
  insulators; the list marks them.
- The experimental structure named with a compound has another space group than the calculated entry shown for 3,384
  compounds, and another composition within 2 at.% for 2,308; the record of each candidate says so.
- Of the entries marked experimental that are used, 83% lie within 50 meV/atom of their source's hull in JARVIS-DFT
  (16,858 of 20,350) and 80% in the Materials Project (37,754 of 47,311).
- JARVIS-DFT: the hull distance was computed for all 93,902 entries (50,656 within 50 meV/atom); a seeded sample of
  300 entries agrees with pymatgen's phase diagram to 0.0 eV/atom.
- 6.4 minutes on a GitHub runner; 1.7 GB of memory at most.

## 7. What follows from this

- Hurricane's list is replaced by screening round 7 (`ml/hurricane9_screen7.py`), which builds the pool from the four
  open sources above and computes the JARVIS-DFT hull distance itself.
- Storm's list still stands as screening round 5 published it, from a pool selected with the field. It needs a
  screening of its own; until then the app says so under the list and shows each candidate's computed distance.
- The background of compounds with no superconductivity record that Hurricane 9.0 learned from, at a low weight, came
  from the same field-selected pool. The released model is kept as it is.
- What the `ehull` field of the file holds was not established; this record states only what was measured in the copy
  of the file named in section 2.
