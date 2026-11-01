"""Private-path CLI support for the three read-only scientific adapters."""
from pathlib import Path
import argparse
import hashlib

BUNDLE = Path(__file__).resolve().parent
PROJECT = BUNDLE.parents[2]
POLICY = BUNDLE.parent / "protocol" / "normal-state-policy.json"


def arguments(description, *, observed_at=None):
    parser = argparse.ArgumentParser(description=description)
    if not __debug__:
        parser.error("Run without -O: pinned original-source integrity assertions must remain enabled")
    parser.add_argument("--data-root", type=Path, required=True,
                        help="Private batch2 directory containing the cited original files")
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="Private reconstruction directory; never the public bundle")
    parser.add_argument("--project-root", "--repo", dest="project_root", type=Path, default=PROJECT,
                        help="Repository checkout containing ml.normal_state")
    parser.add_argument("--policy", type=Path, default=POLICY,
                        help="Previously frozen extraction policy; defaults to the parent bundle copy")
    if observed_at is not None:
        parser.add_argument("--observed-at", default=observed_at,
                            help="Documented source-inspection time, not a date of measurement")
    args = parser.parse_args()
    args.data_root = args.data_root.resolve(strict=True)
    args.output_dir = args.output_dir.resolve()
    args.project_root = args.project_root.resolve(strict=True)
    args.policy = args.policy.resolve(strict=True)
    if args.output_dir == BUNDLE or BUNDLE in args.output_dir.parents:
        parser.error("Generated curve arrays must stay outside the public bundle")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    return args


def materialize_original_member(path, content, *, source_root):
    """Extract only a named, hash-bound source member; never overwrite bytes."""
    path, root = path.resolve(), source_root.resolve()
    if root not in path.parents:
        raise ValueError("Original member escaped the private data root")
    if path.exists():
        if not path.is_file() or path.read_bytes() != content:
            raise ValueError("Existing original member changed: " + path.name)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()
