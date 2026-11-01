# Rebuilding the experimental source collection

This directory contains the hand-written extraction and adaptation tools from the
November 1, 2026 collection, plus source citations, file hashes, licenses, search
dispositions, and compact audits. It contains no original experimental files,
numeric curve arrays, complete collection, feedback ledger, or fitted model.

The tools preserve the original response quantities, source order, unknown
conditions, source-row identities, and documented curation times. Rebuilding an
observation does not make it a verified normal-state feature or a valid measured
Tc target. The unchanged policy in `protocol/normal-state-policy.json` uses the
absolute 150–300 K window. The low-temperature heat/magnetic batch does not cover
that window.

## Contents

- `root/`: Bi/Ta1.6Te extraction, Nb-C extraction, workbook XML reader, and the
  merge/adjudication step. Source registries and the input-manifest snapshot have
  no curve arrays.
- `storm-sources-hurricane_screen/`: transport normalization and adaptation,
  source-search dispositions, source registry, compact curve indexes and original
  download-file indexes. The full local `scientific-manifest.json` is regenerated
  from original data; it is not distributed here.
- `heat-magnetic/`: exact NbSe2, MgB2, Ta1.6Te and HEA extraction/adaptation,
  source manifest/registry, and the original roundtrip audit. Magnetic moment,
  author M with unknown units, susceptibility, 4πχ, C/T and specific heat remain
  distinct quantities. Heat uses only the declared algebraic T²/C/T conversion.
- `bundle-provenance.json`: original and bundled script hashes, metadata bindings,
  and frozen inspection timestamps. JSON copies preserve content while using LF
  formatting; original byte hashes still identify the private frozen originals.
- `verify_bundle.py`: compilation, metadata, path, content-exclusion and optional
  original-source hash checks. It does not import or run an extraction script.

Counts in collector audits describe their historical batches. They are not counts
of unique observations across adapters. In particular, the HEA magnetic data
appear in both the transport and heat source packages. The copied merge step now
asserts exact equality of 800 finite pairs and excludes the four older transport
aliases from the active collection. See `root/duplicate-adjudications.json` and
`root/hea-duplicate-independent-audit.json`. The heat copy retains unresolved
units/field and its additional missing-response record. This merge does not
rewrite either frozen adapter input or the historical ledger.

## Sources and use permissions

Each source registry contains the paper/dataset citation, inspected locator,
relative original path, hash, and source-specific license. The per-dataset
download indexes record observed download URLs and file hashes, not permissions
for all subsequent uses. Important distinctions in this capture are:

| Source | Recorded dataset terms and limits |
| --- | --- |
| Bi pressure data, [CAM.18197](https://doi.org/10.17863/CAM.18197) | CC BY-NC-ND 4.0; original/derived numeric data kept local. Published resistivity includes the authors' 300 K calibration. |
| Ta1.6Te, [s41467-024-45952-2](https://doi.org/10.1038/s41467-024-45952-2) | CC BY 4.0; transport, magnetic and heat specimens remain separate. |
| Nb-C microstrip, [s41467-020-16987-y](https://doi.org/10.1038/s41467-020-16987-y) | CC BY 4.0; replica EDS is not the measured strip's exact composition. |
| Oxford MgB2 datasets, [ZO6MREoYX](https://doi.org/10.5287/bodleian:ZO6MREoYX) and [xr11rwggY](https://doi.org/10.5287/bodleian:xr11rwggY) | Repository terms permit private noncommercial study/research; no blanket CC dataset license was inferred from the papers. Original and derived numeric data stay local. |
| Bristol NbSe2, [3i7a3mzyfbrrp2j871ykh846v0](https://doi.org/10.5523/bris.3i7a3mzyfbrrp2j871ykh846v0) | Repository Non-Commercial Government Licence, separate from the paper's license. Sample numbering/pressure-grid conflicts remain unresolved. |
| NbTiN workflow, [N9/VH0WLV](https://doi.org/10.21979/N9/VH0WLV) | CC BY-NC 4.0 dataset; original XLSX and repository-ingested TSV are distinct files with separate checksums. |
| Other Zenodo datasets | See each source's metadata, including dataset/article license differences. The HEA unit/field ambiguity and conflicting MgB2 column headers are not resolved by assigning guessed values. |

No source acquisition or redistribution is authorized merely by running these
scripts. Downloaders are not bundled: the capture included later manual additions
that an early downloader did not cover. Follow the cited original repositories
and verify the expected bytes. In particular, transport adaptation also requires
the Sn, PtSb and NbSe2 microbolometer additions listed in its source registry;
the latter uses [Zenodo 10613828](https://doi.org/10.5281/zenodo.10613828).

## Private directory layout and dependencies

Use a separate, writable private data directory. Do not run these tools over an
immutable collection or inside this public tools directory: the extractors write
their local output files beside themselves. First copy:

1. `root/*.py` into the private data directory's top level.
2. The transport and heat `*.py` files into subdirectories named exactly
   `storm-sources-hurricane_screen` and `heat-magnetic`.
3. The frozen `protocol/` policy files into its `protocol/` subdirectory.

Restore the original files under the relative paths in the source registries and
download indexes. Preserve archive member names and the `original/`, `extracted/`
and `raw/` directory layout expected by the scripts. A hash/metadata index cannot
replace the original file. Do not run downloaded author notebooks or plotting
scripts as part of this reconstruction.

Python 3.10+ is required. The root/transport numeric readers use the standard
library, Nb-C additionally needs `xlrd`, and the heat readers need `openpyxl`.
Adapter/verification imports require this repository's `ml.normal_state` and
`ml.feedback` plus NumPy. The separate measured-sample pilot also uses pymatgen
and scikit-learn; see `ml/requirements.txt` for the scientific environment.
Use the repository revision associated with the captured policy and audits.
PDF rendering packages are not required to extract the curves.

## Reconstruction order

The commands below are run from the private data directory. `REPO` denotes the
repository checkout; pass its path to the transport adapter and heat verifier.
No command below appends a ledger or fits a model.

```text
python extract_root_curves.py
python extract_nbc.py --observed-at 2026-11-01T13:06:54.455160+00:00

python storm-sources-hurricane_screen/normalize_sources.py
python storm-sources-hurricane_screen/adapt_transport_collection.py --repo REPO --observed-at 2026-11-01T13:16:15.946247+00:00

python heat-magnetic/extract_nbse2.py
python heat-magnetic/extract_additional.py
python heat-magnetic/build_normal_collection.py
python heat-magnetic/verify_collection.py --repo REPO
python heat-magnetic/build_manifest.py

python merge_collection.py
```

`root/correct_hea_duplicates.py` is a separate historical correction utility. It
requires the existing private `feedback.jsonl` history and intentionally appends
800 superseding corrections while checking preservation of the old byte prefix.
It is not part of the reconstruction commands or bundle verification, must not
be run against a new ledger, and is not automatically executed here.

The two `--observed-at` options only replace the original scripts' current-time
calls when reproducing the documented curation. Their defaults retain the
original current-time behavior. These are inspection/availability times, not
invented dates of the underlying historical experiment. The root and heat
extractors already retain their explicitly frozen times.

The heat verifier assumes that no file named `heat-magnetic/no-ledger-written.jsonl`
has been created: it verifies a read-only preparation, not an ingestion. The
separate `ml.normal_state` CLI handles deliberate ingestion; consult that module
for the current interface instead of adding `--append` to reconstruction tools.

Do not compare a fresh output file's bytes to an old snapshot without accounting
for the documented curation time, JSON formatting, source revision and merge
adjudication. Compare raw-input hashes, source point identities, quantities,
conditions and schema decisions. The individual original byte hashes are
retained for exact archival checks. Source registration verifies supplied bytes
and curation locators; a matching hash does not authenticate a paper's scientific
claims or independently verify its experimental conclusions.

The current `ml.normal_state` pilot CLI defaults to a gate without fitting. A
detached `--linked-records` JSON can only gate. A real fit must re-read the original
`--registry`, `--collection`, `--sources-root`, `--ledger` and `--policy`, verify
their binding, and explicitly opt in with `--allow-fit`; the independent-group
and target-criterion minima still apply. For a read-only evidence-bound gate,
run from the repository checkout, substituting private input/output paths:

```text
python -m ml.normal_state --pilot --registry REGISTRY_JSON --collection COLLECTION_JSON --sources-root PRIVATE_DATA_DIRECTORY --ledger EXISTING_PRIVATE_LEDGER --policy POLICY_JSON --output-dir PRIVATE_GATE_OUTPUT
```

This example is not an instruction to fit, append observations, or manufacture
the additional independent groups that the captured pilot lacks.

## Safe verification of this public bundle

From this directory:

```text
python verify_bundle.py
python verify_bundle.py --data-root PRIVATE_DATA_DIRECTORY
```

The optional second command reads only the original paths in the source
registries to check their hashes. It does not read a feedback ledger, run an
extractor, overwrite a collection, or alter scientific rules.
