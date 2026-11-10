# Hurricane 9, first fit: declaration before the run (R-007), version 1

Date: 2026-11-10. Committed before any model was fitted on the datasheet. Report-only: adopted is false, nothing is
released, no candidate is listed and progress.json is not written.

## 1. What is declared

- Protocol: hurricane9-protocol-v1, SHA-256 37478fec876263854a3286539aac92820039d8f5a37a5bc87cd8844d40654987
  (the canonical JSON of PROTOCOL in ml/hurricane9.py; printed by: python ml/hurricane9.py --protocol).
- Code: commit 05aa7fbed00232b6e3d9d1ec64c8745bf2f00a9f on claude/hurricane9.

| File | SHA-256 |
| --- | --- |
| ml/hurricane9.py | 4edc1aa43b99f1b6141dae4d714195690e0ed85ee22036c11c6f7cd0fd1c8cf1 |
| ml/hurricane9_data.py (v0.4, as reviewed) | 61695fcbb78e02168f64c9e4505079fa54ea9fb08af53f7fdc628c73ea4870c6 |
| ml/hurricane9_counts.py (v2) | a53af290170fc917e3360820aca705ee8d56d75c2732881aff07323bd4b91585 |
| ml/hurricane.py | c08672379cbf43f4e2be91aebe43984db3a0dbf5db4e5d75e5abcb27b99960fb |
| ml/hurricane2.py | 962d65e311bb1f1dcdd108f9fec7e751f30d0b77dfd17fea1d2efac6e419008d |
| ml/pipeline.py | f2c29ef1032b24208d5d25ee7bb9ea77534b24c0c9234d633054138065ffca68 |
| tests/test_hurricane9.py | f61dab7d0e72d07f257b208e0794368f61df07872907818f58c6c8a0de213eec |

- Data: MDR SuperCon Datasheet Ver.220808, file 220808_MDR_OAndM.txt, 18,227,757 bytes, SHA-256
  a874ab2472c960ace275b2f97e6b97fae8fae2420513fc94d919d0037f202ff7 (NIMS, https://doi.org/10.48505/nims.3837,
  CC BY 4.0); 3DSC_MP.csv at commit 8d69ca9c94b83d387378549225d3b7c3af85ca42, 9,457,406 bytes, SHA-256
  353b86f9c60505d11a3e25df8312da02ff88fd8e27af05b632dec4739d52eb24. Both are verified by size and hash before parsing.
- The run: stage 2 of .github/workflows/hurricane9-fit.yml calls
  python ml/hurricane9.py --run --expect-protocol-sha256 37478fec876263854a3286539aac92820039d8f5a37a5bc87cd8844d40654987
  and the module refuses to read any data under another hash. A change to PROTOCOL changes the hash; a code fix that
  leaves PROTOCOL untouched would be recorded as an amendment to this file before a rerun.

## 2. What had been looked at when this was frozen

Counts only. No model had been fitted on the datasheet, and no prediction or score had been compared with a Tc value.

- Run 42873383799 (ml/hurricane9_counts.py, report SHA-256
  63dd36fb2a34e95af2683fe2e7176ded6dbdab2b342fd92505d4ba3f96a5695b): new parents and new-parent units per window. It
  fixed the windows of the protocol.
- Run 42900971572 (python ml/hurricane9.py --preflight at commit abf0818abf526a3e70df471a672e43292acd6b69, report
  SHA-256 40cfc552d15b7c6a18174df56129796cac886668d420d86aba4358502caf6bd0): every step of the run except the fit.
  The new-parent units of all seven windows equal the counts of the first run; 16,899 compositions pass through the
  feature code with no feature empty; 2,133 rows of 3DSC_MP are in the five classes of Hurricane 4.0 (2,123 formulas,
  2,104 composition bins). Rows each design is trained on (rows with a Tc value in brackets):

| Reports up to | previous | data, names, measured | transfer | new-parent cuprate units asked, with a Tc value |
| --- | --- | --- | --- | --- |
| 1985 | 255 (130) | 608 (409) | 6,112 (4,694) | 1,253 (new family) |
| 1990 | 490 (332) | 2,004 (1,713) | | 544 |
| 1995 | 932 (697) | 4,770 (4,095) | | 395 |
| 2000 | 1,270 (972) | 7,304 (6,352) | | 115 |
| 2005 | 1,575 (1,206) | 8,761 (7,580) | 15,737 (13,126) | 49 |
| 2010 | 2,027 (1,574) | 10,049 (8,660) | | not in the protocol |
| 2015 | 2,342 (1,841) | 11,251 (9,719) | | not in the protocol |

  Each of the four ladder designs has its regressor and its classifier in every window, and transfer its regressor in
  both of its windows. After that run and before any fit, one rule was tightened: in a new-family window the units of
  other, already known families that pass the 30 K event are left out of the AUC of claim C4 (commit 151c30a). The
  rows and matrices of the run are not touched by that change.

## 3. Question, designs and endpoints (the protocol JSON is authoritative)

Trained only on reports dated up to T, how well does a design rank the units of the parents first reported in the
next five years by their Tc? Test rows are new-parent units: no training unit has their identity or claims one of
their parents. Units whose oxygen content no source field instantiates take no part, nor does the one flagged unit.

- previous: the recipe of Hurricane 4.0 (composition statistics, 15 physics features, element fractions, 19
  stoichiometric structure types; the same learner) trained on the units whose composition bin is in the 3DSC rows
  that model was trained on. A stand-in for that model, not the released file: its Materials Project structure
  block, its background compounds and its abstention have no counterpart in a datasheet row.
- data: the same recipe on every unit of the four modelled families.
- names: data plus the datasheet's structure names.
- measured: names plus the lattice lengths a and c, their ratio, the measured oxygen content as its own column and
  three flags. Every design already sees the oxygen number through the composition.
- transfer: no element identities; fitted only for the two windows in which a family was new (cuprates after 1985,
  iron-based after 2005).
- References: R0, the family median of the training side; R1, the Tc of the nearest known compound.
- Primary endpoint: Spearman rank correlation between predicted Tc and the unit's Tc over the test units with a Tc
  value, per family and window, pooled over the family's windows with the number of parent clusters as weight;
  percentile bootstrap over parent clusters, 1000 replicates, seed 7.

## 4. Claims and decision rule

| Claim | Statement | Contrast | Rows |
| --- | --- | --- | --- |
| C0 | the improved design ranks new cuprate parents better than the previous one | measured minus previous | cuprate, windows after 1990, 1995, 2000, 2005 |
| C1 | more data helps the previous recipe | data minus previous | the same |
| C2 | measured sample variables help where they exist | measured minus names | the same, units with a c axis |
| C3 | the previous recipe on all data beats the nearest known compound | data minus R1 | the same, all units |
| C4 | a design without element identities ranks the 30 K event above chance in a family it never saw | AUC of transfer | each new-family window |

A contrast is pooled over the windows that define both designs. It is met when the pooled difference is positive, its
95% interval excludes zero and those windows hold at least 20 parent clusters. C4 is met per window when the interval
of the AUC lies above 0.5. No correction for the five claims. Everything else in the report is descriptive, including
the other three families, the error in kelvin and the released model's own measure.

## 5. Review

R-007 asks for the other side's no-objection to the frozen hash before a fit on real data. The other agent has been
paused by the project owner since 2026-11-06. On 2026-11-10 the project owner waived that review for this fit
(answer to the question how to handle it: approve directly), on these terms: the protocol is frozen and published
with its hash before the run; the run is report-only; the report and one prediction row per test unit are kept as a
workflow artifact for a later audit. The waiver covers this protocol hash only.

## 6. What this run cannot show

- It is not a test of the released Hurricane 4.0 file. That model was trained without a time cut, on rows from every
  year, so a part of these test units is in its training data, and no datasheet row carries the structure block it
  needs.
- measured uses quantities measured on the sample that was made, so it says whether those variables carry the Tc
  signal that nominal formulas lack. It is not a screening claim: a compound nobody has made has no measured c axis.
- One database, one way of dating reports (the year field of the datasheet) and one parent rule. A parent that is new
  in the datasheet may have been known in the literature earlier.
- A claim that is met here does not release a model. A release needs its own design, review and the owner's merge.
