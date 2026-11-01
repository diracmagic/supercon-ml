# Parallel acquisition for Storm and Hurricane

This batch expands collection to known superconductors, bounded measured
non-superconductors, unlabelled materials and all 152 currently ranked candidates.
Collection and effect evaluation can proceed independently for each track. A
track does not need to wait for the other's result, but each must have source-bound
sample/condition/criterion matches and its own frozen evaluation before fitting.

The existing Storm measured-sample pilot keeps its frozen three transport
features, positive resistive-midpoint target and connected-component holdout.
Five eligible independent singleton pairs still cannot satisfy five training
specimen-conditions in every holdout. More temperature points on those five
specimens do not fix that shortage. Hurricane's new physical-quantity collection
does not yet supply an independently paired, multi-family cohort; no new
physical-quantity LOFO result is claimed. The previously reported Storm 6 and
Hurricane 6/7 experiments remain distinct from this collection.

## NIMS secondary database

This collection used the [MDR SuperCon Datasheet Ver.240322](https://doi.org/10.48505/nims.4487),
made public by the National Institute for Materials Science (NIMS), Center for
Basic Research on Materials. It is licensed CC BY 4.0; the corresponding
[User's Guide v2.0](https://doi.org/10.48505/nims.4488) is retained. This is a
version-pinned secondary literature source, not 34,026 newly verified specimens.

`mdr_catalog.py` verifies all six original input hashes before reading the tables
and attached numeric files. It preserves every nonempty record's original
strings, field names, literature citation and logical row. It retains units and
Tc criteria as written. It does not turn missing records into negative examples,
identify phases by formula, infer numeric dopings from variable formulae, replace
room temperature with exactly 300 K, or use superconducting outcomes as precursor
features. In particular, gamma and Debye-temperature derivations need primary
paper checks before admission as predictors.

The archive has 5,772 files: 5,761 text files and 11 GIFs. Some text explicitly
identifies Plot Digitizer; others retain database axis/series metadata. Both
remain secondary attachments. Numeric pairs are an availability count, not
independent curves or specimens. Multiple series are not silently merged.

```console
python tools/normal_state_collection/batch3/mdr_catalog.py --data-root ORIGINALS --output CATALOG
python -m unittest tests.test_mdr_catalog -v
```

Download links and exact SHA256 values are in `mdr-summary.json` and the script.
The generated full JSONL records, attachment index and original files stay in the
local acquisition archive. No experimental feedback events or training labels
are emitted by this secondary-source importer. `mdr-validation.json` records an
independent every-cell and every-attachment-hash roundtrip.

## Primary sources and candidate inventory

The subdirectories retain source references, availability decisions, original
byte hashes and source-specific extraction tooling. Original paper/figure data
are not embedded in this public bundle. An accessible supplement does not by
itself establish permission to redistribute its full contents. Source scripts
never execute deposited notebooks or launch model training.

The candidate inventory preserves exact ranked structure identity and the
existing predictions in a separately named field. A material-composition match
is only a paper-retrieval lead. It is never a same-specimen measurement or proof
that a predicted phase has been synthesized. Retired candidates stay separate.

All new sources remain retrospective published evidence. This batch changes no
frozen model thresholds and releases no model. Literature, author measurements,
digitized figures, calculations and model predictions remain distinct evidence
domains.

## Copyright and permitted use

Keep article and dataset licences separate. Record the applicable source URL,
version, licence statement and attribution alongside the immutable file hash.
Public access alone is not treated as a redistribution or training licence.
Sources with unresolved permissions remain in local review; this public bundle
contains only tooling, citations, hashes and bounded audit metadata. Check the
applicable permitted uses before admitting any newly collected source to a
training run. An article's noncommercial/no-derivatives terms are not replaced
by a different licence on its separately deposited dataset, or vice versa.

The local NIMS acquisition ZIP is labelled with its dataset's CC BY 4.0 statement,
source DOI, retained bibliographic references and description of the serialization
changes. It is not a combined redistribution of the differently licensed primary
paper attachments in the other collection directories.
