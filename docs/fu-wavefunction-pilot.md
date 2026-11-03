# Lattice Fermi Sets pilot for Storm and Hurricane

This is a report-only research experiment. No production model, candidate score, APP or release is changed.

## Method and attribution

The neural state implements the lattice construction in Liang Fu, **Fermi Sets: Universal and interpretable neural architectures for fermions**, [arXiv:2601.02508v2](https://arxiv.org/html/2601.02508v2): a Jordan–Wigner ordering sign times a permutation-invariant, signed neural coefficient. Our coefficient uses a small self-attention network. Fermion exchange changes the wavefunction sign, and duplicate spin orbitals give zero amplitude.

We optimize the Rayleigh quotient of a specified Hubbard Hamiltonian. Exact configuration summation replaces Monte Carlo because the sectors have only 16, 24 or 36 configurations. Exact eigenstates are used for independent quality checks; they do not enter the gradient or initialize the neural state.

This differs from the continuum Gaussian-attraction superconductivity calculation by Li, Ong, Geier, Lin and Fu, **Attention is all you need to solve chiral superconductivity**, [arXiv:2509.03683v2](https://arxiv.org/html/2509.03683v2). We use finite discrete, spinful, repulsive Hubbard clusters, not their continuum generalized-Slater ansatz or an author-code reproduction. We do not compute a real material's wavefunction, electron-phonon coupling or superconducting Tc. The parameter-conditioned continuum foundation model of Zaklama, Geier and Fu, **Large Electron Model: A Universal Ground State Predictor**, [arXiv:2603.02346v2](https://arxiv.org/html/2603.02346v2), is related context; its weights or dataset are not used here.

## Frozen experiment

The universal bank covers all 11 four-vertex simple graph classes, t=1, U/t=0,4,8 and particle sectors (1 up,1 down), (2 up,1 down), (2 up,2 down). These graphs and parameters are fixed independently of all material labels.

Actual periodic crystal coordinates determine nearest-neighbor graphlet frequencies. Tied neighbor choices are averaged; atom/image identities are retained. Missing or over-budget structures remain explicitly missing. The fixed central-star mapping reaches four of the 11 classes; the complete bank remains prespecified. Atom species do not determine the assumed hopping or U, so this is an unfitted structural electronic surrogate, not a recovered material Hamiltonian.

Four arms share identical material cohorts, folds, downstream estimators and training-only preprocessing:

| Arm | Added inputs |
|---|---|
| Q0 | Existing baseline only |
| QG | Full graphlet frequencies and mapping flags |
| QE | Exact-Hamiltonian energy descriptors and mapping flags |
| QN | Neural-wavefunction energy descriptors and mapping flags |

The 14 energy descriptors include ground energies, correlation energies relative to each solver's own U=0 result, and finite-cluster particle-number curvature. The curvature is not a superconductivity label. QN and QE are deterministic transforms of QG; a benefit would indicate useful representation or regularization, not new electronic information. QG and QE distinguish that benefit from adding topology or approximating an already solvable Hamiltonian.

Storm retains the 7,582-material/4,288-system cohort, chemical-system holdouts, separate full/proper-training heads and group conformal calibration. Hurricane retains the 615-parent, four-family P/U experiment with whole-family and shared-system exclusions and nested alpha selection. Its unlabeled parents are not verified negatives. Previously inspected folds make all comparisons exploratory. Every arm and paired chemical-system bootstrap contrast is reported; adoption is always false.

## Physics preflight and version history

- [V1 declaration](../protocol/fu-lattice-v1.json): two seeds, 300 constant-rate Adam steps. Actual complete CPU run: 82/99 states passed; 17 failed; 23.807 seconds. The failures are retained.
- [V2 declaration](../protocol/fu-lattice-v2.json): four seeds, 2,000 cosine-rate Adam steps. This convergence revision was declared before any real material head was fitted or scored. All accuracy, runtime, mapping and downstream criteria remain unchanged. Actual local run: 99/99 states passed; 196.592 seconds.
- [V2 wording erratum](../protocol/v2-erratum.json): the explicit four-seed list controls execution; inherited prose saying “two” is stale. No numerical setting was changed by this erratum.

The quality gate requires an energy error per site <=0.0025t, state residual <=0.05t and ground-subspace overlap >=0.95, with an explicit variational-bound tolerance. Degeneracy is checked against the whole ground space. Failed neural states are never replaced with exact states under the QN name. Runtime estimates and timings apply to the recorded local CPU environment, not every runner.

The workflow first validates a shared wavefunction bank, then starts the two material comparisons. Full-cohort material comparisons completed in [CI run41578153170](https://github.com/diracmagic/supercon-ml/actions/runs/41578153170), scientific source `79f6ebe05de381108cf2f04c7cd3430039633c67`. The four locally available original CIFs support mapping checks, not a full-cohort result. Exact parsed structures, source/CIF hashes, weights, traces, Hamiltonians, splits, per-row predictions and package/hardware records are retained as research evidence. No unknown-license external wavefunction dataset was downloaded.

## First full-cohort results

| Same-run metric | Q0 baseline | QG topology | QE exact surrogate | QN neural surrogate |
|---|---:|---:|---:|---:|
| Storm DFT-Tc MAE, K (lower is better) |0.963758|0.966361|0.969456|0.969976|
| Storm top-decile MAE, K |3.677685|3.710931|3.716741|3.723047|
| Hurricane equal-family observed-P/U AUC (higher is better) |0.604001|0.600788|0.592432|0.592432|
| Hurricane equal-family recall at20% ranking budget |24.7740%|24.3889%|24.3779%|24.3779%|

QN minus Q0 gives Storm MAE **+0.006218 K**, paired95% interval **[-0.002408,+0.015164] K**, and Hurricane AUC **-0.011569**, interval **[-0.032179,+0.013871]**. Neither meets the prespecified practical-gain rule. All comparisons reuse historical folds and are exploratory. The same-run Q0 is the reference; historical cross-run MAE changes are not credited to this method.

The exact surrogate also supplies no improvement. Hurricane QN and QE produce identical rankings; QN is worse than graph-only QG in this exploratory AUC comparison (difference-0.008356, interval[-0.015482,-0.002639]). These results assess this unweighted structural surrogate, rather than every possible material-specific variational-wavefunction calculation.

Storm's neural-arm group interval coverage rises from89.9254% to90.5084%, while mean width rises from5.3863 to5.5315K and interval score worsens from8.0724 to8.2439K. Coverage alone is not a reliability improvement. Mapping covers7571/7582 Storm structures and610/615 Hurricane parents; every original row remains in all arms.

No model is adopted or released. A future attempt to add new electronic information requires justified material-specific Hamiltonian parameters or independently computed electronic/phonon data; this graph transformation does not provide them.
