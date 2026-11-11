# Screening round 6, the candidates of Hurricane 9.0: declaration before the run (R-007), version 1

Date: 2026-11-11. Committed with the module, before it was run on any real data. Until this file is on the branch, the
module refuses to read any data: python ml/pipeline.py hurricane9screen stops unless the protocol hash below is written
here.

## 1. What is declared

- Protocol: hurricane9-screen-protocol-v1, SHA-256 e0d088da29803a7a40f07b43683d34f1e87460e65bf6bfc6358ff12117dc2dcf
  (the canonical JSON of PROTOCOL in ml/hurricane9_screen.py; printed by: python ml/hurricane9_screen.py --protocol).
  It binds the release protocol hurricane9-release-protocol-v1, SHA-256
  87694b5845afb729f2f1ede376e194a48db8c65dd7d800f169af34521b1a1fdf, under which Hurricane 9.0 was released on
  2026-11-11 (results/validation/hurricane9-release-declaration-v1.md).
- Code: the files below, committed together with this declaration on the branch claude/hurricane9-screen.

| File | SHA-256 |
| --- | --- |
| ml/hurricane9_screen.py | 8903b5254376d11df59194e2a6271890912dbacca1642dd88c7eaf8f8309fc3e |
| ml/hurricane9_release.py (the release module, unchanged) | 6b13d19af83ef958cb5897725f825d55d83de10983077513bd163e95807b31a5 |
| ml/hurricane9.py (unchanged) | 4edc1aa43b99f1b6141dae4d714195690e0ed85ee22036c11c6f7cd0fd1c8cf1 |
| ml/hurricane9_data.py (unchanged) | 61695fcbb78e02168f64c9e4505079fa54ea9fb08af53f7fdc628c73ea4870c6 |
| ml/hurricane3.py (unchanged) | add5b2f15689dfdf75e8479cc58fb6912900e63d9626eec2a3db565418c1f960 |
| ml/screen.py (unchanged) | 42b74504c6cd2d5cbc365504d76b4dba752f3a3df7ff0fc842f02ae7867d8242 |
| ml/radar.py (unchanged) | c5664c7c19d6eb18f1598e7f5ce7baef1fb169a7f11004dd3987ff56e8474d57 |
| ml/literature_audit.py (unchanged) | 3f7ea509c40c86a2090bdc5f98b0cdef9dabce230d9453dd43fa9721d0830e25 |
| ml/pipeline.py | fbe497bbdeff6d722a600698aae185eab63184647f3de669284d684c4cba09e1 |
| data/checks.json (unchanged) | a277bc9e2c37656686dbc55fd01f48e921fd55294452e509e430d1497854a91a |
| tests/test_hurricane9_screen.py | 2417b8c8e9be2e6ffbf6f4ef662ebe9d14e7d196c7dab3761a441df8c6083f3d |
| tests/test_screen_publication.py | 0c9a53927a701c803d2051fae6cf558b6e81eb6262973c30f9b4d47af6e15ca8 |
| .github/workflows/train.yml | 974a0b380f38e42ee7aca93905faf2084898c676eb078fd121e806a1daed583a |
| results/validation/hurricane9-screen-publication.json | 1414f3874e5dbe8243b41fc91d3cfa4bf6af75ffed026af73a8b26086063985d |
| results/validation/screening-round5-hurricane-list.json | a33dcbf0518ad1bee972421647a40ce80eef538315a2e6f733715a70e985ab40 |

- What the run does. It screens Hurricane's pool with the version in use and writes Hurricane's list of candidates.
  The published list was screened by Hurricane 4.0 in screening round 5. No design is fitted, compared or released:
  the run repeats the released computation of ml/hurricane9_release.py for the pool (the training rows, the guard
  with its three numbers, the regressor) and writes its answers down.
- The pool is the one the release run built for its guard (hurricane9_release.jarvis_background): Hurricane's
  screening pool from JARVIS-DFT, built as screen.run builds it, with the exclusions of the earlier rounds, without
  the compounds whose composition the datasheet lists. Radar, refitted on its 3DSC rows, routes each compound.
- The chance of a compound is the cross-fitted chance of the guard: it comes from a classifier that learned from no
  background compound of the compound's fold. The run must reproduce the table the release run committed
  (results/hurricane_round9_background.csv, SHA-256
  e2575e5481cf6734f0e03b9b9741ba6fbba168d460a20589ccbc34a279c12500): the same compounds in the same order, the same
  routing, the same not-known answers and every chance within 5.1e-5 (the table is rounded to four decimals). If
  anything differs, for instance because JARVIS-DFT changed, the run stops and writes nothing.
- The Tc if a compound superconducts is the released regressor's. Its 90% range uses the released width on
  log(1 + Tc), read from results/hurricane_round9.json.
- The list: the compounds Radar sends to Hurricane that lie inside its training data, ordered by the chance times
  the Tc, then the Tc, then the JARVIS id; one per chemical system; at most 50. A compound outside the training data
  is not known: counted, not listed.
- What is written: results/screen_round6.json, results/screen_round6_hurricane.csv (every compound Radar sent, with
  its answer), and in progress/progress.json the fields screen.hurricane and screen.models, the line of the screen
  stage and one log entry. The run is made twice with the same code: first by hand on the branch, where the workflow
  commits nothing and the block is read from the job log; then, after the merge, by hand on main.

## 2. What had been looked at when this was frozen

- The table of the release run is committed, so the pool (3,881 compounds), Radar's routing (591 sent), which of
  those Hurricane judges (54, in 42 chemical systems) and the chance of each were known and had been read: one
  compound has a chance of at least one half (0.71; it is the single false alarm of the guard check), the next
  0.45. Of the 50 compounds of the published list, 23 are among the 54; the other 27 are not known to Hurricane 9.0.
- Not known when this was written: the Tc the regressor predicts for any of these compounds, hence the order of the
  list, the ranges, the nearest training compound of each and which compound of a chemical system is listed. The
  module had run only on invented rows (its --smoke and tests/test_hurricane9_screen.py).
- Nothing was chosen with this knowledge. The model, the guard and the routing are those of the release, the
  ordering rule and the limit of one candidate per chemical system are those of the earlier screening rounds, and
  the run reproduces the committed table or stops.

## 3. The rule

There is no decision to take. The list is published as computed, whatever it shows, including a short list. Nothing
is tuned and rerun under this protocol; a different pool, routing, order or model needs a new protocol and a new
declaration.

## 4. How this stands to the earlier rounds and their audit

- Screening round 5 produced both lists in one run, and its publication was audited
  (results/validation/screening-app-publication.json). This round replaces Hurricane's list only. Storm's list, its
  tracks, ranges and phonon checks are not touched: results/validation/hurricane9-screen-publication.json records,
  before the run, the two fields of the screen block the run may replace, and the audited list is kept in
  results/validation/screening-round5-hurricane-list.json. After the run, putting the two values back must give the
  audited screen hash for hash (tests/test_screen_publication.py).
- The five-member spread of round 5 (p_lo, p_hi) is not produced. The chance of Hurricane 9.0 comes from one
  classifier for each background fold, and no spread is invented for it.
- A check recorded in data/checks.json is attached as before, with the exact-ID corrections of the literature audit.
  That audit (2026-11-01) covers the 152 candidates of round 5. A compound that is new on the list has no literature
  record until a search is recorded for it, and the app says so.

## 5. Review

R-007 asks for the other side's no-objection to the frozen hash before a run on real data. The other agent has been
paused by the project owner since 2026-11-06. On 2026-11-11 the owner chose the full replacement of Hurricane 4.0
with a new screening round to follow and to approve the release fits directly, and after the release asked for the
candidates of Hurricane 9.0 in the app. This run is made on that request without a review by the other side; the
owner was told so before the run. The terms are those of the release: the protocol is frozen and published with its
hash before the run, nothing is tuned, and the result, with one row for every compound Radar sent, is kept in
results/ for a later audit.

## 6. What this list cannot show

- A chance of at least one half is weak evidence. Among parent compounds first reported after its training data end,
  Hurricane 9.0 gave such a chance to 72.8% of the compositions that superconduct and to 38.5% of those measured not
  to superconduct. The one compound of the pool with such a chance is, read the other way, the false alarm of the
  guard check: the same compounds serve as probable negatives and as candidates.
- The compounds have no superconductivity record in the checked sources, which is not a measurement and not a
  literature search. Some are hypothetical structures; the list says which are linked to ICSD.
- The Tc is a rough guide: for new cuprate parents the model ranks by Tc with 0.62 against 0.57 for the Tc of the
  nearest known compound, which it does not clearly beat.
- The model reads the composition only. Polymorphs get one answer, and the structure shown is the most stable
  JARVIS-DFT entry of the composition.
- The list is short because Hurricane 9.0 does not judge 91% of the compounds Radar sends it. That is its answer,
  not a gap to fill.
