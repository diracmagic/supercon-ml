"""Validate the reviewed external-research registry and build its offline UI bundle.

Edit the source manifest/parts after reviewing primary evidence, then run this
script. --check verifies deterministic bytes without writing. No network fetch,
model update or claim of a completed scheduled review is performed here.
"""
from __future__ import annotations

import argparse
from datetime import date
import ipaddress
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data' / 'external_research_memo.json'
OUTPUT = ROOT / 'app' / 'dist' / 'external-research-data.js'
MAX_FILE_BYTES = 70_000
STATUSES = {'completed', 'current', 'not_reported'}
CATEGORIES = {'计算预测', '回溯验证', '实验研究', '数据与工具', '研究计划'}
REQUIRED_TEXT = ('id', 'heading', 'short', 'year', 'stage', 'headline', 'team',
                 'publication', 'result', 'boundary', 'reference_point', 'title',
                 'category', 'evidence_type', 'pressure', 'tc_criterion', 'verified_version')


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def text(value: object, label: str) -> None:
    require(isinstance(value, str) and bool(value.strip()), f'{label}: non-empty text required')
    require(not any(ord(c) < 32 and c not in '\n\t' for c in value), f'{label}: control character')


def iso_date(value: object, label: str) -> None:
    text(value, label)
    require(bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', value)), f'{label}: ISO date required')
    date.fromisoformat(value)


def safe_url(value: object) -> None:
    text(value, 'URL')
    require(not any(c.isspace() or ord(c) < 32 for c in value), 'URL: whitespace/control character')
    require(not any(ord(c) < 32 for c in unquote(value)), 'URL: encoded control character')
    require('\\' not in value, 'URL: backslash disallowed')
    parsed = urlsplit(value)
    require(parsed.scheme == 'https' and bool(parsed.hostname), 'URL: HTTPS host required')
    require(parsed.username is None and parsed.password is None, 'URL: credentials disallowed')
    require(parsed.port in (None, 443), 'URL: unexpected port')
    host = parsed.hostname.lower()
    require(host != 'localhost' and '.' in host, 'URL: public hostname required')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        require(bool(re.fullmatch(r'[a-z0-9.-]+', host)), 'URL: invalid hostname')
    else:
        require(address.is_global, 'URL: private/local address disallowed')


def read_json(path: Path) -> dict:
    raw = path.read_bytes()
    require(len(raw) <= MAX_FILE_BYTES, f'{path.name}: exceeds reviewable file-size limit')
    obj = json.loads(raw.decode('utf-8'))
    require(isinstance(obj, dict), f'{path.name}: object required')
    return obj


def load_registry(source: Path = SOURCE) -> dict:
    source = source.resolve()
    data = read_json(source)
    require(data.get('schema_version') == 1, 'Unsupported schema version')
    require('entries' not in data, 'Manifest must reference reviewable entry parts')
    parts = data.get('entry_parts')
    require(isinstance(parts, list) and bool(parts), 'Manifest entry_parts required')
    require(len(parts) == len(set(parts)), 'Duplicate part reference')
    entries = []
    for name in parts:
        require(isinstance(name, str) and bool(re.fullmatch(r'external-research-memo/part-\d{2}\.json', name)), 'Invalid part path')
        path = (source.parent / name).resolve()
        require(path.is_relative_to(source.parent), 'Part path escapes registry directory')
        part = read_json(path)
        require(part.get('schema_version') == 1 and isinstance(part.get('entries'), list), 'Invalid entry part')
        entries.extend(part['entries'])
    require(type(data.get('entry_count')) is int and data['entry_count'] == len(entries), 'Entry count mismatch')
    data = {key: value for key, value in data.items() if key not in ('entry_parts', 'entry_count')}
    data['entries'] = entries
    validate_registry(data)
    return data


def validate_registry(data: dict) -> None:
    require(data.get('schema_version') == 1, 'Unsupported schema version')
    for field in ('updated', 'reviewed_on'):
        iso_date(data.get(field), field)
    require(data['reviewed_on'] <= data['updated'], 'Review date cannot follow update date')
    schedule = data.get('schedule')
    require(isinstance(schedule, dict), 'Schedule metadata required')
    require(schedule.get('frequency') == 'daily', 'Expected daily search schedule')
    require(bool(re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', str(schedule.get('time', '')))), 'Invalid schedule time')
    require(schedule.get('timezone') == 'America/Chicago', 'Unexpected schedule timezone')
    require(schedule.get('status') in {'planned', 'active_schedule', 'paused'}, 'Schedule status is not review completion')
    text(schedule.get('note'), 'Schedule note')
    if schedule['status'] == 'active_schedule':
        text(schedule.get('automation_id'), 'Active schedule automation ID')
    entries = data.get('entries')
    require(isinstance(entries, list) and bool(entries), 'Entries required')
    ids = []
    for entry in entries:
        require(isinstance(entry, dict), 'Entry object required')
        for field in REQUIRED_TEXT:
            text(entry.get(field), field)
        entry_id = entry['id']
        require(bool(re.fullmatch(r'\d{2,4}', entry_id)), 'Stable numeric entry ID required')
        ids.append(entry_id)
        require(entry['category'] in CATEGORIES, f'{entry_id}: invalid category')
        require(bool(re.fullmatch(r'\d{4}', entry['year'])), f'{entry_id}: year required')
        iso_date(entry.get('reviewed_on'), f'{entry_id} review date')
        require(entry['reviewed_on'] <= data['reviewed_on'], f'{entry_id}: future entry review date')
        safe_url(entry.get('url'))
        doi = entry.get('doi')
        if doi:
            require(bool(re.fullmatch(r'10\.\d{4,9}/[^\s<>]+', doi)), f'{entry_id}: invalid DOI')
        else:
            require(entry['category'] == '研究计划', f'{entry_id}: research DOI required')
            text(entry.get('source_label'), f'{entry_id}: announcement source label')
        refs = entry.get('primary_refs')
        require(isinstance(refs, list) and bool(refs), f'{entry_id}: primary references required')
        for ref in refs:
            require(isinstance(ref, dict), f'{entry_id}: reference object required')
            text(ref.get('label'), f'{entry_id}: reference label')
            safe_url(ref.get('url'))
        require(any(ref['url'] == entry['url'] for ref in refs), f'{entry_id}: citation missing from references')
        for extra in entry.get('extra', []):
            require(isinstance(extra, list) and len(extra) == 2, f'{entry_id}: invalid extra reference')
            text(extra[0], f'{entry_id}: extra label')
            safe_url(extra[1])
        steps = entry.get('progress_steps')
        require(isinstance(steps, list) and bool(steps), f'{entry_id}: progress required')
        for step in steps:
            require(isinstance(step, dict), f'{entry_id}: progress object required')
            for field in ('kind', 'label', 'detail'):
                text(step.get(field), f'{entry_id}: progress {field}')
            require(step.get('status') in STATUSES, f'{entry_id}: progress status invalid')
            if entry['category'] != '实验研究' and step['kind'] in {'synthesis', 'measurement', 'phase_validation', 'replication'}:
                require(step['status'] == 'not_reported', f'{entry_id}: prediction/plan cannot claim an experimental stage')
    require(len(ids) == len(set(ids)), 'Duplicate stable entry ID')
    require(ids == sorted(ids, key=int), 'Entries must be in stable numeric ID order')


def bundle_bytes(data: dict) -> bytes:
    validate_registry(data)
    body = json.dumps(data, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
    # Defensive escaping even if the same payload is later embedded in HTML.
    for char, escape in (('<', '\\u003c'), ('>', '\\u003e'), ('&', '\\u0026'), ('\u2028', '\\u2028'), ('\u2029', '\\u2029')):
        body = body.replace(char, escape)
    output = ('// Generated by tools/build_external_research.py; edit the reviewed registry.\n'
              'globalThis.SuperconExternalResearch = ' + body + ';\n').encode('utf-8')
    require(len(output) <= MAX_FILE_BYTES, 'Bundle exceeds offline reviewable file-size limit')
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--check', action='store_true', help='Validate source and compare generated bytes without writing')
    args = parser.parse_args(argv)
    try:
        data = load_registry(args.source)
        output = bundle_bytes(data)
        if args.check:
            require(args.output.exists() and args.output.read_bytes() == output,
                    'External research bundle is missing or stale; run tools/build_external_research.py')
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(output)
    except (ValueError, OSError, TypeError) as error:
        print(f'External research validation failed: {error}', file=sys.stderr)
        return 1
    print(f'External research: {len(data["entries"])} entries, {len(output)} bytes; ' + ('verified' if args.check else 'built'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
