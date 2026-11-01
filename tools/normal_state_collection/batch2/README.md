# Replaying the second source collection

This bundle contains three source adapters, registries, compact audits and search
dispositions. It contains no original PDF, archive, author notebook, full curve
array, feedback ledger or fitted model. The adapters and aggregate step never
read or write a ledger and never fit a model.

The existing extraction policy is unchanged: absolute 150-300 K window, 200/225/250 K
anchors, no extrapolation, and one statistical unit per physical specimen and
condition. Source inspection took place before model fitting, after some paper
Tc values and temperature ranges had already been inspected. This is retrospective
curation, not a blinded or prospective discovery test.

| Source | Recorded source and disposition |
| --- | --- |
| NbN reference film | [Author paper](https://arxiv.org/abs/2504.18997), [published DOI](https://doi.org/10.1088/1361-6668/adeaf2), [numerical source](https://doi.org/10.6084/m9.figshare.29339720.v1), CC BY 4.0. One 9.6 nm reference NbN film, 52,439 figure-source points, reported half-R(20 K) Tc=8.5 K. The same author-curated Fig.3 trace supports a checked link. Its logical trace identity does not prove one uninterrupted hardware acquisition. P/B remain unknown. Adjacent NbN/Mo bilayers are not encoded as homogeneous formulas. |
| Pure-Al reference in NitrAl study | [Paper](https://doi.org/10.1088/1361-6668/ad20fc), [source archive](https://doi.org/10.5281/zenodo.10194875), CC BY 4.0. Three separate raw I-V/T routines yield 310 resistance estimates. The archive identifies specimen code 0r2v3/CD45/C1. Table2 reports a midpoint for reference A, but does not explicitly map A to that exact piece. **No checked target links** are exported. Neither matching process labels nor similar Tc resolves this identity gap. |
| YRu3B2 | [Author paper](https://arxiv.org/abs/2512.09314), [source archive](https://doi.org/10.5281/zenodo.18276373), CC BY 4.0. Two separate traces, 103,325 retained records, including null resistance readings. The reported midpoint is 0.78 K. Identical notebook dimensions are circumstantial same-bar evidence; **no checked links** are exported. |

The Al and YRu3B2 target facts can be retained as historical evidence without
assigning those facts to the broad-temperature curves. Neither adds a matched
training sample. No alternative condition-unreported sensitivity protocol is
implemented here. Five singleton components still fail the frozen LOCO gate:
holding one out leaves four training samples, below the required five.

## Original files and private layout

Use a private directory outside this public bundle. `source-inputs.json` lists the
five required original files, direct download URLs, byte sizes and SHA256 values.
Download the cited originals manually and check those values. A changed source
version is a new curation task, not permission to weaken a checksum.

The private layout is:

```text
PRIVATE_PARENT/
  previous/                       earlier collection and its original sources
    combined-registry.json
    combined-collection.json
  batch2/                         --data-root
    transport/raw/nbn_mo_data.zip
    transport/raw/nbn_mo_paper.pdf
    thermo/nitral-2024/source.zip
    thermo/nitral-2024/paper.pdf
    validation/raw/YRu3B2_data.zip
  replay/                         --output-dir / --collections-root
```

Only explicitly named original archive members are extracted under the private
`batch2/` directory. Existing member bytes must match and are never overwritten.
Author notebooks are read as original source bytes, never executed. The
reconstructed point arrays and reports are written under `replay/`, not Git.

The NbN file named `nbn_mo_paper.pdf` must be the pinned author PDF. The publisher
PDF URL returned HTML during collection; that response is neither included nor
treated as the inspected article. The YRu3B2 source archive is sufficient for its
numeric replay; the inspected paper is available through the linked author HTML.

Python 3.10+ with NumPy and pandas is required. Use the repository scientific
environment so `ml.normal_state` and `ml.feedback` are importable. PDF rendering,
Torch, MACE and author plotting dependencies are not required by these adapters.
The default `--project-root` is the repository containing this bundle. The default
policy is the unchanged parent `../protocol/normal-state-policy.json` copy.

## Reconstruction

From a repository checkout, substitute private paths for the capitalized names:

```text
python tools/normal_state_collection/batch2/transport/adapt_batch2.py --data-root PRIVATE_PARENT/batch2 --output-dir PRIVATE_PARENT/replay --project-root REPO
python tools/normal_state_collection/batch2/thermo/build_nitral_collection.py --data-root PRIVATE_PARENT/batch2 --output-dir PRIVATE_PARENT/replay --project-root REPO
python tools/normal_state_collection/batch2/validation/adapt_yru3b2.py --data-root PRIVATE_PARENT/batch2 --output-dir PRIVATE_PARENT/replay --project-root REPO

python tools/normal_state_collection/batch2/aggregate.py --data-root PRIVATE_PARENT/batch2 --previous-root PRIVATE_PARENT/previous --collections-root PRIVATE_PARENT/replay --output-dir PRIVATE_PARENT/replay/combined
```

Each adapter preserves its documented inspection timestamp by default. The
optional `--observed-at` changes that curation/availability time, not the date of
the experiment; it therefore intentionally changes collection and event hashes.
Do not use it to backdate new evidence. `--policy` can select the same frozen file
elsewhere; scientific rule changes are rejected by the current module.

The transport and Al registries resolve original `raw_path` values against
`--data-root`; the YRu3B2 registry resolves them against `--data-root/validation`.
Aggregation verifies each source in that declared directory, checks duplicate
IDs, and rebases only registry paths to the common `PRIVATE_PARENT` source root.
Curves, targets and links are unchanged. Input-manifest and batch-note references
use directory roles so they contain no machine-specific absolute paths.

If the private `--data-root/observation-corrections.json` exists, aggregation
explicitly carries its list into both generated collections. Each entry must
contain exactly `curve_id`, `point_index`, `supersedes` and `reason`. It is never
inferred from matching values or renamed IDs, and aggregation does not apply it.
The historical Al metadata correction removed an unverified A label from 310
observations without changing any numeric point, target or training link; see
`root/al-correction-plan.json`. Its ledger-specific 310 observation identities
are not published. A new ledger needs no such correction map. Reuse with an
existing history requires its own explicit matching map and the ingestion
module's complete history/point-binding checks; the public count/hash summary
cannot substitute for those identities.

The captured replay adds six curves, 156,074 records, three historical target
facts and one checked link. With the captured previous collection the aggregate
has 48 sources, 109 curves, 316,988 records, ten targets and six checked links.
These are collection counts, not counts of trainable independent samples.

## Verification and provenance

```text
python tools/normal_state_collection/batch2/verify_bundle.py
python tools/normal_state_collection/batch2/verify_bundle.py --data-root PRIVATE_PARENT/batch2 --replay-root PRIVATE_PARENT/replay
```

The verifier compiles source text without executing an adapter, checks compact
metadata/checksums, rejects full curve arrays, binary/ledger files and local
absolute paths, and optionally checks original/replayed files. The recorded
default replay reproduced all three private collection files byte for byte.
Aggregate scientific arrays and rebased registry content also matched; only
role-based audit path references differ from the original local aggregation.

`bundle-provenance.json` records original and bundled script hashes and the
unchanged extraction-function ASTs. `replay-validation.json` records the actual
replay comparison. Audit fields named `used_point_indices_summary` contain a
count and canonical SHA256 of the omitted list, not the point indices or values.
Source hashes bind bytes and curated locators; they do not independently
authenticate experimental claims. Search records preserve access failures and
source exclusions instead of treating absent data as negative observations.

## Deliberate ingestion and model gate

The following are separate, explicit examples for a private ledger. They are not
executed by bundle reconstruction or verification. Do not re-create an existing
ledger or alter earlier observations to match regenerated timestamps.

```text
python -m ml.normal_state --registry PRIVATE_PARENT/replay/combined/registry.json --collection PRIVATE_PARENT/replay/combined/collection.json --sources-root PRIVATE_PARENT --ledger EXISTING_PRIVATE_LEDGER --policy tools/normal_state_collection/protocol/normal-state-policy.json --output-dir PRIVATE_PARENT/ingest-report --append

python -m ml.normal_state --pilot --registry PRIVATE_PARENT/replay/combined/registry.json --collection PRIVATE_PARENT/replay/combined/collection.json --sources-root PRIVATE_PARENT --ledger EXISTING_PRIVATE_LEDGER --policy tools/normal_state_collection/protocol/normal-state-policy.json --output-dir PRIVATE_PARENT/pilot-gate
```

The second command is the evidence-bound gate, without fitting. A future
deliberate fit would use that same complete input chain and explicitly add
`--allow-fit`; it must still pass every frozen criterion, independent-component
and training-sample gate. The captured data do not pass those gates. No example
overrides them, labels an untested material negative or upgrades Storm's DFT Tc
model to an experimentally validated predictor.
