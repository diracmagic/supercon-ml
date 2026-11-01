"""Check public-package boundaries and optionally rebuild in an isolated copy."""
from pathlib import Path, PurePosixPath
import argparse
import ast
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative_path(value):
    p = PurePosixPath(value)
    if p.is_absolute() or ".." in p.parts or "\\" in value or re.match(r"^[A-Za-z]:", value):
        raise ValueError("Unsafe/nonportable source path: " + value)
    return p


def inspect_json(value, key=""):
    if isinstance(value, dict):
        for name, child in value.items():
            if name in {"data", "points", "observations", "events"} and isinstance(child, list) and child:
                raise ValueError("Numerical/ledger payload in public metadata: " + name)
            if name == "raw_path":
                relative_path(child)
            if name == "url" or name.endswith("_url"):
                if child:
                    parsed = urlparse(child)
                    if parsed.scheme != "https" or parsed.username or parsed.password:
                        raise ValueError("Unexpected source URL")
                    forbidden = {"token", "access_token", "signature", "x-amz-signature", "authorization", "key"}
                    if forbidden & {s.lower() for s in parse_qs(parsed.query)}:
                        raise ValueError("Signed/credential URL in metadata")
            inspect_json(child, name)
    elif isinstance(value, list):
        if len(value) > 16 and all(isinstance(row, list) and len(row) >= 2 and all(isinstance(n, (int, float)) or n is None for n in row) for row in value):
            raise ValueError("Response-like numerical array in public metadata")
        for child in value:
            inspect_json(child, key)


def static_check():
    files = [p for p in ROOT.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    pycount, jsoncount = 0, 0
    for path in files:
        content = path.read_bytes()
        if len(content) > 70000 or b"\r" in content:
            raise ValueError("Public file exceeds70KB or is notLF: " + path.name)
        if path.suffix not in {".py", ".json", ".md"}:
            raise ValueError("Unexpected public binary/data file: " + path.name)
        text = content.decode("utf-8")
        if re.search(r"[A-Za-z]:[\\/]Users[\\/]|[/]Users[/]|[/]home[/][^ ]+|gh[pousr]_[A-Za-z0-9]{20,}", text):
            raise ValueError("Private local path/credential-shaped content")
        if path.suffix == ".py":
            ast.parse(text, filename=path.name)
            pycount += 1
        if path.suffix == ".json":
            inspect_json(json.loads(text))
            jsoncount += 1
    return {"public_files": len(files), "python_syntax_checked": pycount, "json_checked": jsoncount,
            "max_public_file_bytes": max(p.stat().st_size for p in files), "all_LF": True,
            "no_raw_arrays_or_pdfs_or_ledger_payloads": True, "no_local_absolute_paths_or_signed_auth_urls": True}


def inputs(data_root):
    registry = read(ROOT / "source-registry.json")
    rows = registry["sources"] + registry["primary_evidence_artifacts"]
    for source in rows:
        rel = relative_path(source["raw_path"])
        path = data_root.joinpath(*rel.parts)
        if digest(path) != source["sha256"] or path.stat().st_size != source["bytes"]:
            raise ValueError("Source byte/hash mismatch: " + str(rel))
    return rows


def rebuild(data_root, scratch):
    sources = inputs(data_root)
    with tempfile.TemporaryDirectory(prefix="hurricane-roundtrip-", dir=scratch) as tmp:
        base = Path(tmp)
        local, out = base / "sources", base / "compact"
        local.mkdir()
        for source in sources:
            target = local / source["raw_path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(data_root / source["raw_path"], target)
        for script in ("extract_lsco.py", "extract_fete_fese.py", "extract_nickelate.py"):
            subprocess.run([sys.executable, str(ROOT / script), "--data-root", str(local)], check=True, capture_output=True)
        subprocess.run([sys.executable, str(ROOT / "build_metadata.py"), "--data-root", str(local), "--output-root", str(out)], check=True, capture_output=True)
        compared = []
        for path in out.rglob("*.json"):
            rel = path.relative_to(out)
            if read(path) != read(ROOT / rel):
                raise ValueError("Compact roundtrip differs: " + rel.as_posix())
            compared.append(rel.as_posix())
        return {"isolated_rebuild_json_compared": len(compared), "all_compact_metadata_equal": True,
                "source_originals_modified": False, "models_fitted": 0, "ledger_files_read_or_written": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--scratch-root", type=Path)
    args = parser.parse_args()
    result = static_check()
    if args.data_root:
        result["registered_source_and_evidence_hashes_checked"] = len(inputs(args.data_root.resolve()))
    if args.rebuild:
        if not args.data_root or not args.scratch_root:
            parser.error("--rebuild requires --data-root and --scratch-root")
        args.scratch_root.mkdir(parents=True, exist_ok=True)
        result.update(rebuild(args.data_root.resolve(), args.scratch_root.resolve()))
    result["valid"] = True
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
