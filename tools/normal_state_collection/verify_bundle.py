"""Read-only checks for public curation tooling; no extractor or ledger is run."""
from pathlib import Path
import argparse
import ast
from datetime import datetime
import hashlib
import json
import re
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parent
RAW_SUFFIXES = {'.csv', '.tsv', '.tab', '.dat', '.zip', '.xlsx', '.xls', '.pdf', '.png', '.jsonl', '.pyc'}
DRIVE_PATH = re.compile(r'(?<![A-Za-z0-9])[A-Za-z]:[\\/](?!/)')
UNIX_LOCAL = re.compile(r'^/(?:Users|home|mnt|tmp|var|private)(?:/|$)')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def walk(value, location='$'):
    if isinstance(value, dict):
        require(not isinstance(value.get('points'), list), f'Numeric curve points embedded: {location}')
        require(not isinstance(value.get('data'), list), f'Original/derived data array embedded: {location}')
        require('event_type' not in value, f'Ledger event embedded: {location}')
        for key, child in value.items():
            yield from walk(child, location + '.' + key)
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from walk(child, f'{location}[{i}]')
    elif isinstance(value, str):
        require(not DRIVE_PATH.search(value) and not UNIX_LOCAL.search(value), f'Local absolute path: {location}')
        if value.startswith(('https://', 'http://')):
            url = urlsplit(value)
            require(url.username is None and url.password is None, f'URL credentials: {location}')
            for key, _ in parse_qsl(url.query):
                lower = key.lower()
                require(not any(word in lower for word in ('signature', 'credential', 'token', 'password', 'api_key', 'access_key')),
                        f'Signed/authenticated query parameter: {location}:{key}')
        yield location, value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, help='Optional private original-source root; reads registry-listed originals only')
    args = parser.parse_args()
    # Unit tests import the new read-only parser. Ignore interpreter caches;
    # all publishable source/metadata files still undergo the checks below.
    files = sorted(p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.relative_to(ROOT).parts)
    json_documents, py_files = {}, []
    for path in files:
        name = path.relative_to(ROOT).as_posix()
        require(path.suffix.lower() not in RAW_SUFFIXES, f'Raw data/ledger/binary file included: {name}')
        require(not name.endswith('collection.json'), f'Complete collection included: {name}')
        require(path.stat().st_size <= 70_000, f'File exceeds independently readable70KB limit: {name}')
        text = path.read_text(encoding='utf-8')
        require(not DRIVE_PATH.search(text), f'Absolute local drive path in {name}')
        require('\r' not in text, f'Non-LF source formatting in {name}')
        if path.suffix == '.py':
            tree = ast.parse(text, filename=name)
            compile(tree, name, 'exec')  # Compile only. Never execute/import the extractor.
            py_files.append(name)
        elif path.suffix == '.json':
            json_documents[name] = json.loads(text)
            list(walk(json_documents[name], name))

    provenance = json_documents['bundle-provenance.json']
    for record in provenance['scripts'] + provenance['metadata']:
        path = ROOT / record['path']
        require(path.is_file() and sha(path) == record['bundled_sha256'], 'Bundled file hash mismatch: ' + record['path'])
    require(all(record['ast_equal_after_removing_only_documented_cli_additions'] for record in provenance['scripts']),
            'Source algorithm AST comparison missing')
    require(all(record['same_json_content'] for record in provenance['metadata']), 'Metadata content changed during copy')
    for times in provenance['frozen_inspection_timestamps'].values():
        for timestamp in times:
            require(datetime.fromisoformat(timestamp.replace('Z', '+00:00')).tzinfo is not None, 'Naive inspection timestamp')

    policy = json_documents['protocol/normal-state-policy.json']
    canonical = json.dumps(policy, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    canonical_hash = hashlib.sha256(canonical).hexdigest()
    require(canonical_hash == (ROOT / 'protocol/normal-state-policy.sha256').read_text().strip(), 'Frozen policy canonical hash changed')

    compact = json_documents['storm-sources-hurricane_screen/scientific-manifest.compact.json']
    for index in compact['curve_indexes']:
        document = json_documents[index['path']]
        require(document['source_id'] == index['source_id'], 'Curve index source mismatch')
        require(len(document['curve_index']) == index['curves'], 'Curve index count mismatch')
        require(all('data' not in curve and 'points' not in curve for curve in document['curve_index']), 'Curve array in compact index')

    aliases = json_documents['root/duplicate-adjudications.json']
    require(len(aliases) == 4 and sum(row['duplicate_finite_points'] for row in aliases) == 800, 'HEA adjudication metadata incomplete')
    merge_tree = ast.parse((ROOT / 'root/merge_collection.py').read_text())
    merge_aliases = next(ast.literal_eval(node.value) for node in merge_tree.body
                         if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'ALIASES' for t in node.targets))
    require(merge_aliases == {row['excluded_curve_id']: row['retained_curve_id'] for row in aliases}, 'Merge aliases differ from adjudication')
    independent = json_documents['root/hea-duplicate-independent-audit.json']
    require(all(pair['raw_csv_identical_bytes'] and pair['same_numeric_prefix'] for pair in independent['pairs']), 'Independent duplicate check failed')
    require(all('heat_additional_points' not in pair for pair in independent['pairs']), 'Additional original numeric point in public audit')

    private_files_checked = 0
    if args.data_root is not None:
        data_root = args.data_root.resolve()
        cache = {}
        for name in ('root/root-registry.json', 'root/nbc-registry.json',
                     'storm-sources-hurricane_screen/transport-registry.json', 'heat-magnetic/heat-registry.json'):
            for source in json_documents[name]['sources']:
                relative = Path(source['raw_path'])
                require(not relative.is_absolute(), 'Absolute original-source path')
                path = (data_root / relative).resolve()
                require(data_root in path.parents, 'Original source escaped private data root')
                require(path.suffix.lower() != '.jsonl', 'Registry must not reference a ledger')
                require(path.is_file(), 'Missing original source: ' + source['raw_path'])
                if path not in cache:
                    cache[path] = sha(path)
                require(cache[path] == source['sha256'], 'Original source hash mismatch: ' + source['raw_path'])
        private_files_checked = len(cache)

    print(json.dumps({'status': 'pass', 'files': len(files), 'python_syntax_checked': len(py_files),
                      'json_documents_checked': len(json_documents), 'max_file_bytes': max(p.stat().st_size for p in files),
                      'source_bound_script_copies': len(provenance['scripts']),
                      'metadata_copies_content_preserved': len(provenance['metadata']),
                      'policy_canonical_sha256': canonical_hash,
                      'hea_aliases_checked': len(aliases), 'private_original_files_sha256_checked': private_files_checked,
                      'extractors_executed': 0, 'ledger_files_read_or_written': 0,
                      'raw_or_full_collection_files_bundled': 0, 'absolute_local_paths_or_authenticated_urls': 0}, indent=2))


if __name__ == '__main__':
    main()
