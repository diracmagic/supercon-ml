"""Combine inspected local collections without rewriting immutable source curves."""
from pathlib import Path
import json
import hashlib

ROOT = Path(__file__).resolve().parent
PARTS = [('root-registry.json', 'root-collection.json'),
         ('nbc-registry.json', 'nbc-collection.json'),
         ('storm-sources-hurricane_screen/transport-registry.json', 'storm-sources-hurricane_screen/transport-collection.json'),
         ('heat-magnetic/heat-registry.json', 'heat-magnetic/heat-collection.json')]
QUALITY = {
    'brown2018:Bip27s': ('reported_sample_formula', 'Brown et al., Sci Adv 4 eaao4793 (2018), Methods: elemental bismuth single crystal and Fig1 pressure series.'),
    'tokumoto2024:rho': ('nominal_sample_formula', 'Tokumoto et al., Nat Commun 15,1529 (2024), Methods sample preparation and Fig2: nominal Ta1.6Te quasicrystal, minor approximant impurity retained.'),
    'sn-run1-broad-2p5': ('reported_sample_formula', 'Sasaki et al., Phys Rev B111,104513 (2025), Fig4a inset and experiment: elemental tin film run1 under 2.5 GPa.'),
    'ptsb-2026-Fig2a-30nm': ('nominal_sample_formula', 'Muller et al., Phys Rev Materials10,094801 (2026), Fig2a and structural characterization: nominal epitaxial PtSb 30 nm film.'),
    'nbs2-No28-dev4-broad': ('nominal_sample_formula', 'Wang et al., ACS Nano15,18403 (2021), Fig3b and SI device No28dev4: nominal 2H NbS2, reported sulfur defects; exact defect fraction unknown.'),
}
ALIASES = {
    'hea-x0.35-ZFC': 'hea_2022_measured_x0p35_zfc',
    'hea-x0.35-FC': 'hea_2022_measured_x0p35_fc',
    'hea-x0.71-ZFC': 'hea_2022_measured_x0p71_zfc',
    'hea-x0.71-FC': 'hea_2022_measured_x0p71_fc',
}

def main():
    registry, collection = {'sources': []}, {'curves': [], 'targets': [], 'links': []}
    seen, manifest = {k: set() for k in ['sources', 'curves', 'targets']}, []
    for registry_name, collection_name in PARTS:
        r = json.loads((ROOT / registry_name).read_text(encoding='utf-8'))
        c = json.loads((ROOT / collection_name).read_text(encoding='utf-8'))
        for key, rows, field in [('sources', r['sources'], 'source_id'), ('curves', c['curves'], 'curve_id'), ('targets', c.get('targets', []), 'target_id')]:
            for row in rows:
                assert row[field] not in seen[key], (key, row[field])
                seen[key].add(row[field])
                (registry if key == 'sources' else collection)[key].append(row)
        for link in c.get('links', []):
            link = dict(link)
            if link['curve_id'] in QUALITY:
                link['composition_quality'], link['composition_source_locator'] = QUALITY[link['curve_id']]
            collection['links'].append(link)
        manifest.append({'registry': registry_name, 'collection': collection_name,
                         'registry_sha256': hashlib.sha256((ROOT / registry_name).read_bytes()).hexdigest(),
                         'collection_sha256': hashlib.sha256((ROOT / collection_name).read_bytes()).hexdigest(),
                         'curves': len(c['curves']), 'points': sum(len(x['points']) for x in c['curves']),
                         'targets': len(c.get('targets', [])), 'links': len(c.get('links', []))})
    by_id = {c['curve_id']: c for c in collection['curves']}
    duplicates = []
    for old, kept in ALIASES.items():
        a = [(p['temperature_k'], p['value']) for p in by_id[old]['points'] if p['value'] is not None]
        b = [(p['temperature_k'], p['value']) for p in by_id[kept]['points'] if p['value'] is not None]
        assert a == b, ('Duplicate adjudication no longer matches raw pairs', old, kept)
        duplicates.append({'excluded_curve_id': old, 'retained_curve_id': kept, 'duplicate_finite_points': len(a),
                           'reason': 'Exact same source CSV values collected twice; retain unknown unit/field and original missing row. Historical ledger observations are corrected append-only.'})
    collection['curves'] = [c for c in collection['curves'] if c['curve_id'] not in ALIASES]
    collection['duplicate_adjudications'] = duplicates
    for name, data in [('combined-registry.json', registry), ('combined-collection.json', collection), ('combined-input-manifest.json', manifest), ('duplicate-adjudications.json', duplicates)]:
        (ROOT / name).write_text(json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(',', ':'))+'\n', encoding='utf-8')
    print(json.dumps({'parts': manifest, 'sources': len(registry['sources']), 'curves': len(collection['curves']),
                      'points': sum(len(c['points']) for c in collection['curves']), 'targets': len(collection['targets']), 'links': len(collection['links'])}))

if __name__ == '__main__':
    main()
