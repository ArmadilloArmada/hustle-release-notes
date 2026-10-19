"""Human-approve drafted release notes and social blurbs before export."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

APPROVAL_FILENAME = "approval.json"
REQUIRED_ARTIFACTS = ("release-notes.md", "social.md")


def artifact_paths(out_dir: Path) -> dict[str, Path]:
    return {name: out_dir / name for name in REQUIRED_ARTIFACTS}


def file_digest(path: Path) -> dict[str, int | str]:
    data = path.read_bytes()
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
    }


def load_approval(out_dir: Path) -> dict | None:
    path = out_dir / APPROVAL_FILENAME
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise SystemExit(f"Invalid approval file: {path}")
    return data


def verify_approval(out_dir: Path) -> dict:
    """Return approval record if present and still matches current artifacts."""
    approval = load_approval(out_dir)
    if approval is None:
        raise SystemExit(
            "No approval found. Run `python src/main.py approve --yes` after reviewing "
            f"{', '.join(REQUIRED_ARTIFACTS)}."
        )

    files = approval.get("files")
    if not isinstance(files, dict):
        raise SystemExit("Approval record is missing file digests; re-approve.")

    for name, path in artifact_paths(out_dir).items():
        if not path.is_file():
            raise SystemExit(f"Approved artifact missing: {path}")
        current = file_digest(path)
        recorded = files.get(name) or {}
        if recorded.get("sha256") != current["sha256"]:
            raise SystemExit(
                f"{name} changed since approval. Re-run "
                "`python src/main.py approve --yes` after review."
            )
    return approval


def _preview(path: Path, *, max_chars: int = 600) -> str:
    text = path.read_text(encoding="utf-8")
    if len(text) <= max_chars:
        return text.rstrip() + "\n"
    return text[:max_chars].rstrip() + "\n…\n"


def approve_artifacts(
    out_dir: Path,
    *,
    yes: bool,
    show_preview: bool = True,
) -> Path:
    """Record human approval for out/release-notes.md and out/social.md."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = artifact_paths(out_dir)
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise SystemExit(
            "Missing draft(s): "
            + ", ".join(missing)
            + ". Run `python src/main.py draft` first."
        )

    print("Human review required before export / paste / mailto.")
    print("Artifacts:")
    digests: dict[str, dict[str, int | str]] = {}
    for name, path in paths.items():
        digests[name] = file_digest(path)
        print(f"  - {path} ({digests[name]['bytes']} bytes, sha256={digests[name]['sha256'][:12]}…)")
        if show_preview:
            print(f"--- preview {name} ---")
            print(_preview(path))

    if not yes:
        try:
            answer = input(
                "Approve these drafts for free export (mailto/Discord paste)? [y/N] "
            ).strip().lower()
        except EOFError:
            answer = ""
        if answer not in {"y", "yes"}:
            raise SystemExit("Approval cancelled. No approval.json written.")

    record = {
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "approved_by": "human",
        "files": digests,
        "note": (
            "Human approved offline. Export may write mailto/Discord paste snippets; "
            "no Discord/email API send."
        ),
    }
    approval_path = out_dir / APPROVAL_FILENAME
    approval_path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Approved. Wrote {approval_path}")
    return approval_path
