"""Fetch exact inspected author bytes to --source-root/storm/raw, then extract.

No repository data, ledger or model is modified. An existing mismatched file is
never replaced. Metadata and numeric files are kept together in the original ZIP.
"""
from pathlib import Path
import argparse
import hashlib
import urllib.request
import zipfile

FILES = [
    ('diamond4inch-paper.pdf', 'https://arxiv.org/pdf/2609.15282v1',
     'd9832c9ae7f78930b91308a650872ad91d5ea739311793862adce06590f55eff'),
    ('diamond4inch-data.zip', 'https://ndownloader.figshare.com/files/70393047',
     '21e12aa4e9d7a68aae6bafc2145ef5fb02b6dd09c841bfbf8403999bfbceade3'),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', required=True, type=Path,
                        help='New collection root; files go into its storm/raw subdirectory')
    args = parser.parse_args()
    raw = args.source_root.resolve() / 'storm/raw'
    raw.mkdir(parents=True, exist_ok=True)
    for filename, url, expected in FILES:
        path = raw / filename
        if path.exists():
            data = path.read_bytes()
        else:
            data = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent':'supercon-ml-source-reproduction/1'}), timeout=60).read()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f'Original source hash mismatch: {filename}; refusing a different source version')
        if not path.exists():
            path.write_bytes(data)
    target = (raw / 'diamond4inch').resolve()
    with zipfile.ZipFile(raw / 'diamond4inch-data.zip') as archive:
        for member in archive.infolist():
            destination = (target / member.filename).resolve()
            if not destination.is_relative_to(target):
                raise ValueError('Archive path escaped the explicit extraction directory')
            if destination.exists() and destination.is_file():
                if destination.read_bytes() != archive.read(member):
                    raise ValueError('Existing extracted source bytes differ')
        archive.extractall(target)
    print('Original source hashes verified; extraction complete. No ledger or model was written.')


if __name__ == '__main__':
    main()
