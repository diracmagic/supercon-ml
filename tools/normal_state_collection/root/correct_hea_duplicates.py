"""Append explicit source-curation corrections; never remove historical events."""
import copy
import hashlib
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / 'supercon-ml'))
from ml import feedback as F
from merge_collection import ALIASES

REASON = ('Independent source audit: original CSV columns are T,M without a unit; the paper caption reports '
          '5/50 Oe whereas the author plotting code divides both traces by 5 or 5.187. Raw signal unit and '
          'field are unresolved. These exact finite pairs duplicate the retained heat adapter; no training eligibility.')

def main():
    path = ROOT / 'feedback.jsonl'
    ledger = F.FeedbackLedger(path)
    events = ledger.read()
    old_size = path.stat().st_size
    old_file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    originals = [e for e in events if e['event_type'] == 'observation' and
                 e['payload'].get('curve_id') in ALIASES and e['supersedes'] is None]
    assert len(originals) == 800, len(originals)
    payloads, hashes = [], []
    for old in originals:
        p = copy.deepcopy(old['payload'])
        p.update(quantity='author_M_channel', unit=None, correction_reason=REASON,
                 duplicate_of_curve_id=ALIASES[p['curve_id']], exclude_from_training=True,
                 evidence_adjudication='hea-cross-adapter-2026-11-01')
        p['conditions']['field_T'] = None
        p['coordinates']['magnetic_field_t'] = None
        p['feature_eligible'] = False
        # This is a correction to the source interpretation, not a new claim to
        # match the old frozen curve's unit/coordinates/content hash.
        p['superseded_curve_content_sha256'] = p.pop('curve_content_sha256')
        payloads.append(p)
        hashes.append(old['hash'])
    result = ledger.append_observations(payloads, supersedes=hashes)
    with path.open('rb') as handle:
        assert hashlib.sha256(handle.read(old_size)).hexdigest() == old_file_hash
    audit = dict(corrections=len(result), corrected_original_hashes=hashes,
                 correction_hashes=[e['hash'] for e in result], original_prefix_bytes=old_size,
                 original_prefix_sha256=old_file_hash, original_prefix_preserved=True,
                 duplicate_aliases=ALIASES, reason=REASON)
    (ROOT / 'hea-ledger-corrections.json').write_text(json.dumps(audit, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in audit.items() if k not in ['corrected_original_hashes', 'correction_hashes']}))

if __name__ == '__main__':
    main()
