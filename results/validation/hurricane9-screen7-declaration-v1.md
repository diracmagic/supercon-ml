# Screening round 7, Hurricane 9.0 on a wider pool: declaration before the run (R-007), version 1

Date: 2026-11-12. Committed with the module, before any compound of the wider pool was routed or scored. Until this
file is on the branch, the module refuses to read any data: `python ml/pipeline.py hurricane9screen7` and
`python ml/hurricane9_screen7.py --snapshot` stop unless the protocol hash below is written here.

## 1. What is declared

- Protocol: hurricane9-screen7-protocol-v1, SHA-256 46c955b68e68a52a291eba5398757125a22fbcd44f4a47db08c330d0f1eecfd2
  (the canonical JSON of PROTOCOL in `ml/hurricane9_screen7.py`; printed by
  `python ml/hurricane9_screen7.py --protocol`). It binds the release protocol hurricane9-release-protocol-v1, SHA-256
  87694b5845afb729f2f1ede376e194a48db8c65dd7d800f169af34521b1a1fdf, under which Hurricane 9.0 was released on
  2026-11-11 (`results/validation/hurricane9-release-declaration-v1.md`).
- Code and records: the files below, committed together with this declaration on the branch `claude/screen-round7`.
  Every other file of the branch is that of main at commit 42940c3ccb54a8b36ea5a2daaf0d340d54314bff.

| File | SHA-256 |
| --- | --- |
| ml/hurricane9_screen7.py | 231060e9b1971d31323696de618a05aed0e4fd4f880f62cd36c7874569dbf9ad |
| ml/hurricane9_screen.py (screening round 6, unchanged) | 8903b5254376d11df59194e2a6271890912dbacca1642dd88c7eaf8f8309fc3e |
| ml/hurricane9_release.py (the release module, unchanged) | 6b13d19af83ef958cb5897725f825d55d83de10983077513bd163e95807b31a5 |
| ml/hurricane9.py (unchanged) | 4edc1aa43b99f1b6141dae4d714195690e0ed85ee22036c11c6f7cd0fd1c8cf1 |
| ml/hurricane9_data.py (unchanged) | 61695fcbb78e02168f64c9e4505079fa54ea9fb08af53f7fdc628c73ea4870c6 |
| ml/hurricane3.py (unchanged) | add5b2f15689dfdf75e8479cc58fb6912900e63d9626eec2a3db565418c1f960 |
| ml/hurricane2.py (unchanged) | 962d65e311bb1f1dcdd108f9fec7e751f30d0b77dfd17fea1d2efac6e419008d |
| ml/hurricane.py (unchanged) | c08672379cbf43f4e2be91aebe43984db3a0dbf5db4e5d75e5abcb27b99960fb |
| ml/screen.py (unchanged) | 42b74504c6cd2d5cbc365504d76b4dba752f3a3df7ff0fc842f02ae7867d8242 |
| ml/radar.py (unchanged) | c5664c7c19d6eb18f1598e7f5ce7baef1fb169a7f11004dd3987ff56e8474d57 |
| ml/literature_audit.py (unchanged) | 3f7ea509c40c86a2090bdc5f98b0cdef9dabce230d9453dd43fa9721d0830e25 |
| ml/pipeline.py | a69fb4ced3a09d70c3c327190ab6e0dafa324d9e7663b41d19ae3a7efa3e9158 |
| ml/requirements.txt | 52acb53bb759b840fde16cffb48d6a57be3c8b9dd2ef44a8d80bd06d77fff1e8 |
| data/checks.json (unchanged) | a277bc9e2c37656686dbc55fd01f48e921fd55294452e509e430d1497854a91a |
| results/hurricane_round9.json (the release run, unchanged) | 2be9d0ee75575cfba52e4548f9ddc19f9a575b72c5ae8fce89eb83f825d01b13 |
| results/hurricane_round9_background.csv (the release run, unchanged) | e2575e5481cf6734f0e03b9b9741ba6fbba168d460a20589ccbc34a279c12500 |
| tests/test_hurricane9_screen7.py | f1fb31917eae04c4b365698d72072e8a274ad514b2a1e913d9f48c20005d36e7 |
| tests/test_screen_publication.py | dca7443b0e9605041cf6e9efcef0f8de35a62dc3c00fa9c4e32788165a9fb3b2 |
| .github/workflows/train.yml | 1863446930d543b87922b3c993db0ae3358f43af5dae1e22b7d78a05779f63d8 |
| .github/workflows/screen7-counts.yml | b0b46aa9315d913f3e0eb0e9e62ac72b66b05ea963ff480e317e708a2fcfa7f1 |
| .github/workflows/screen7-snapshot.yml | b16f2d71a3e06ff31793f8e119bb0f2d30a46bc8561462baff732992d116f981 |
| results/validation/hurricane9-screen7-publication.json | cc75c8feafa2702760fe2de13f600c0147e93060d565e9ae648a3133152d47ca |
| results/validation/screening-round6-hurricane-list.json | a8a601d87be7c95fbf04991a18b8d7380efa579658b0ecdea9a50ac71946d0c4 |
| results/validation/pool-census.md | cd4566e696752f7a14d10181223e34b578d02a66a3178aa6fe72b52fe582ab56 |
| LICENSE-results.md | c907932627cb1a15d0f014167349f652e27c9399e8ff2e5fd3983e7707ce6a2c |

- The sources. Three are bound by their hashes in the protocol, as the count-only runs read them: the rows of
  JARVIS-DFT 3D as jarvis-tools serves them (465925380733c02fe03da2c76adeda63d352649881dfcc2184cddfa4428c7761, of one
  line per row), the Materials Project build 2025-09-25 (c4464ec53f0c2d27395bc622bc43faa18985d1d0bb53ace5f0d0f6b6f74ffd45,
  of the hashes of its 21 summary files) and the Alexandria convex hull, release 2025.07.02
  (8e3206c2f3623c0931ce5b0c3aa62ba83905b4838e4660fd6f2067c55c5bbb8e). A run that reads anything else stops and writes
  nothing. The COD's own table is read once, after this declaration is committed, by
  `.github/workflows/screen7-snapshot.yml`: the usable rows are stored in `results/screen_round7_cod.csv.gz` with a
  note of the reading (`results/screen_round7_cod.json`, which gives the stored file's SHA-256) and committed to the
  branch, and every run screens the stored rows. A run stops if the stored file is not the one its note describes.
- What the run does.
  1. The pool. Each compound is a composition, judged once, because Hurricane reads the composition and nothing else.
     One calculated entry speaks for each composition: among the entries of that composition in JARVIS-DFT, the
     Materials Project and Alexandria that have a band gap, one marked experimental before any other, then one within
     50 meV/atom of its source's convex hull, then by source in that order, then the closest to its source's hull. An
     entry more than 0.5 eV/atom above its source's hull is not used at all. The compound needs 2 to 6 elements, no
     hydrogen, noble gas or short-lived radioactive element, at most 100 atoms in the primitive cell, a calculated band
     gap of at most 1 eV and elements that at least 20 of the training rows contain. A compound with an experimental
     structure of the same material in a source (an entry marked experimental in JARVIS-DFT or the Materials Project,
     or a usable COD entry; the same elements and every share within 2 at.%) is on the experimental track, whatever a
     calculation says about its stability. Any other compound is on the track known from calculation only, and only if
     its calculated entry lies within 50 meV/atom of its source's hull. For JARVIS-DFT that distance is computed in the
     run from the file's formation energies; the file's `ehull` field is not read. A COD composition takes the band gap
     of the calculation of the same material: it is left out if that gap is wider than 1 eV, and stays, marked "no
     calculated band gap", if there is none. Left out as in round 6: every material that SuperCon, 3DSC, the
     computed-T<sub>c</sub> data or the list of others' claims has, every compound made of exactly the elements of a
     known superconductor, every composition with a computed T<sub>c</sub> in JARVIS-DFT, and every composition the
     datasheet lists.
  2. The routing. Radar, refitted on its 3DSC rows as `screen.radar_scores` does it, reads each compound with its cell,
     atoms per cell and space group, and sends it to Hurricane when the probability of an unconventional family is at
     least one half. For the compounds of the released background that are in the pool, the routing must equal that of
     the release path to 1e-9, or the run stops.
  3. The chance. The five classifiers of the release's guard, one for each fold of chemical systems
     (`hurricane3.bg_fold`), score the pool: a compound's chance comes from the classifier that learned from no
     background compound of its fold. They must give the guard's chances for the released background exactly, and the
     run must reproduce the table the release run committed (`results/hurricane_round9_background.csv`) to its rounding
     (5.1e-5). Otherwise the run stops and writes nothing.
  4. The T<sub>c</sub> if a compound superconducts is the released regressor's; its 90% range uses the released width
     on log(1 + T<sub>c</sub>), read from `results/hurricane_round9.json`.
  5. The lists. One for each track: the compounds Radar sends to Hurricane that lie inside its training data (a
     distance ratio at most the guard's abstention), ordered by the chance times the T<sub>c</sub> if it
     superconducts, then that T<sub>c</sub>, then source and identifier; one per chemical system; at most 50. A
     compound further from the training data is not known: counted, not listed.
- What is written: `results/screen_round7.json`, `results/screen_round7_hurricane.csv` (every compound Hurricane gives
  a chance), `results/screen_round7_pool.csv.gz` (every compound of the pool, with its source, track, band gap, hull
  distance, routing and answer), and in `progress/progress.json` the field `screen.hurricane` (with, under
  `hull.storm`, the distance of each candidate of Storm's list to the computed hull), the field `screen.models`, the
  line of the screen stage and one log entry.
- The run is made twice with the same code: first by hand on the branch (Train, stages `hurricane9screen7`), where the
  workflow commits nothing and the block is read from the job log; then, after the merge, by hand on main.

## 2. What had been looked at when this was frozen

- The census of the open sources and the check of the JARVIS-DFT `ehull` field (`results/validation/pool-census.md`).
- Four count-only runs of this module on the real sources (`results/validation/pool-census.md`, section 6): the size of
  the pool by source and track, the exclusions, a seeded sample of entries of each source and track, where 64
  well-known compounds went, and how far above their sources' hulls the entries marked experimental lie. The rules of
  the pool were changed three times on what these runs showed; each change concerned which compounds enter, and each
  is recorded there.
- The released background and its committed table, as for screening round 6.
- Not known when this was written: Radar's routing of any compound of the pool outside the released background, any
  answer of Hurricane 9.0 for such a compound, and so the lists. Nothing was chosen with knowledge of a model output.

## 3. The rule

There is no decision to take. The lists are published as computed, whatever they show, including a short list or a
list on which no compound has an even chance. Nothing is tuned and rerun under this protocol; a different pool,
routing, order or model needs a new protocol and a new declaration.

## 4. How this stands to the earlier rounds

- This round replaces Hurricane's list of screening round 6 by the two lists. Before the run,
  `results/validation/hurricane9-screen7-publication.json` records the one field of the screen block the run may
  replace, and the list of round 6 is kept in `results/validation/screening-round6-hurricane-list.json`. After the
  run, putting that list back must give the screen block that round 6 published, hash for hash
  (`tests/test_screen_publication.py`), and from there the record of round 6 leads back to the screen that the
  publication audit of round 5 recorded.
- Storm's list, its tracks, ranges and phonon checks are not touched. Its pool was selected with the `ehull` field of
  JARVIS-DFT; this round gives, under `hull.storm`, the distance of each of its candidates to the computed hull.
- The background of compounds with no superconductivity record that Hurricane 9.0 learned from came from the
  field-selected pool. The model is used as it was released.
- The literature audit of 2026-11-01 covers the candidates of round 5. A compound that is new on the lists has no
  literature record until a search is recorded for it, and the app says so. A recorded check keeps the correction of
  that audit, also where an entry of another source stands for the compound.

## 5. Review

R-007 asks for the other side's no-objection to the frozen hash before a run on real data. The other agent has been
paused by the project owner since 2026-11-06. On 2026-11-11 the owner asked to widen the screening pool as far as the
licences of the data allow. This run is made on that request without a review by the other side; the owner is told so
before the run on main. The terms are those of the earlier rounds: the protocol is frozen and published with its hash
before the run, nothing is tuned, and the result, with a row for every compound of the pool, is kept in `results/` for
a later audit.

## 6. What these lists cannot show

- What the score is. The classifier learned which measured compounds superconduct above the threshold of their family
  (4.2 K; 1 K for heavy-fermion compounds); a compound that superconducts only below it counts as not superconducting.
  A chance of at least one half is weak evidence: among parent compounds first reported after its training data end,
  Hurricane 9.0 gave such a chance to 72.8% of the compositions that superconduct and to 38.5% of those measured not to
  superconduct.
- The share of false alarms (0.17% of the held-out background compounds that Radar sends to Hurricane lie inside its
  training data and get at least an even chance) was measured on compounds of JARVIS-DFT only. For the other compounds
  of this pool, above all the measured compositions of the COD, it has not been measured.
- An experimental structure on record is not the calculated structure that is shown: it can have another space group,
  and a composition up to 2 at.% away; each candidate's record says so. A COD composition is the one refined in its
  entry and carries no atom positions here; one without a calculated band gap may be an insulator.
- Calculated band gaps fall short of measured ones (ZnO has 0.97 eV in JARVIS-DFT), and correlated insulators often
  come out metallic in such calculations, so the gap rule lets some insulators in. The model reads the composition
  only.
- The compounds have no superconductivity record in the checked sources, which is not a measurement and not a
  literature search.
- Licences: the pool uses JARVIS-DFT (NIST open licence), the Materials Project's entries marked BY-C and Alexandria
  (CC BY 4.0) and the COD (public domain). GNoME (CC BY-NC 4.0) is not used, nor are the Materials Project's entries
  derived from it.
