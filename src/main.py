#!/usr/bin/env python3
"""CLI: fetch GitHub releases → draft → human approve → free export pack."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml

from approve import approve_artifacts
from draft import draft_for_release
from export_pack import build_export_pack
from fetch import fetch_releases

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config.yaml"
OUT_DIR = ROOT / "out"


def load_config(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(
            f"Config not found: {path}\n"
            "Copy config.example.yaml to config.yaml and edit as needed."
        )
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise SystemExit("Config must be a YAML mapping")
    return data


def parse_repo(repo: str) -> tuple[str, str]:
    parts = repo.strip().strip("/").split("/")
    if len(parts) != 2 or not all(parts):
        raise SystemExit(f"Invalid repo '{repo}'; expected owner/name")
    return parts[0], parts[1]


def cmd_draft(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    repo = args.repo or cfg.get("repo") or "cli/cli"
    owner, name = parse_repo(str(repo))
    limit = int(args.limit or cfg.get("release_limit") or 1)
    product_name = str(cfg.get("product_name") or name)
    tone = str(cfg.get("tone") or "friendly and clear")
    openai_model = str(cfg.get("openai_model") or "gpt-4o-mini")

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    print(f"Fetching up to {limit} release(s) from {owner}/{name} …")
    releases = fetch_releases(owner, name, limit=limit, token=token)
    if not releases:
        raise SystemExit(f"No releases found for {owner}/{name}")

    primary = releases[0]
    print(f"Drafting from {primary.tag} ({primary.name}) …")
    bundle = draft_for_release(
        primary,
        product_name=product_name,
        tone=tone,
        openai_model=openai_model,
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    notes_path = OUT_DIR / "release-notes.md"
    social_path = OUT_DIR / "social.md"
    notes_path.write_text(bundle.release_notes, encoding="utf-8")
    social_path.write_text(bundle.social, encoding="utf-8")

    # Draft rewrite invalidates prior approval
    approval_path = OUT_DIR / "approval.json"
    if approval_path.is_file():
        approval_path.unlink()
        print("Cleared stale approval.json (drafts rewritten).")

    print(f"Mode: {bundle.mode}")
    print(f"Wrote {notes_path.relative_to(ROOT)}")
    print(f"Wrote {social_path.relative_to(ROOT)}")
    print("Next: review files, then `python src/main.py approve --yes`.")
    print("No Discord/email API send.")
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    approve_artifacts(OUT_DIR, yes=args.yes, show_preview=not args.no_preview)
    print("Next: `python src/main.py export` (or `export --dry-run`).")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    cfg = load_config(args.config) if args.config.is_file() else {}
    export_cfg = cfg.get("export") if isinstance(cfg.get("export"), dict) else {}
    mailto_to = args.mailto_to or str(export_cfg.get("mailto_to") or "")
    email_subject = args.subject or str(export_cfg.get("email_subject") or "")

    build_export_pack(
        OUT_DIR,
        mailto_to=mailto_to,
        email_subject=email_subject,
        dry_run=args.dry_run,
    )
    if args.print_mailto and not args.dry_run:
        mailto_path = OUT_DIR / "export" / "mailto.url"
        if mailto_path.is_file():
            print("mailto (draft only — open locally if desired):")
            print(mailto_path.read_text(encoding="utf-8").strip())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Rewrite public GitHub releases into customer-facing notes and social "
            "blurbs, then human-approve and export a free paste/mailto pack."
        )
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Path to config YAML (default: {DEFAULT_CONFIG})",
    )
    sub = parser.add_subparsers(dest="command")

    draft_p = sub.add_parser(
        "draft",
        help="Fetch releases and write out/release-notes.md + out/social.md",
    )
    draft_p.add_argument(
        "--repo",
        help="Override config repo (owner/name), e.g. cli/cli",
    )
    draft_p.add_argument(
        "--limit",
        type=int,
        help="Override how many recent releases to fetch (uses latest for drafts)",
    )
    draft_p.set_defaults(func=cmd_draft)

    approve_p = sub.add_parser(
        "approve",
        help="Human-approve current out/ drafts (writes out/approval.json)",
    )
    approve_p.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Record approval without interactive prompt (still requires files on disk)",
    )
    approve_p.add_argument(
        "--no-preview",
        action="store_true",
        help="Skip printing draft previews",
    )
    approve_p.set_defaults(func=cmd_approve)

    export_p = sub.add_parser(
        "export",
        help="Write out/export/ pack (Markdown + mailto + Discord paste); no API send",
    )
    export_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be written without creating files",
    )
    export_p.add_argument(
        "--mailto-to",
        default="",
        help="Optional recipient for mailto.url (draft only)",
    )
    export_p.add_argument(
        "--subject",
        default="",
        help="Optional email subject override",
    )
    export_p.add_argument(
        "--print-mailto",
        action="store_true",
        help="Print mailto URL after export (still no API send)",
    )
    export_p.set_defaults(func=cmd_export)

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Backward compatible: bare flags / no subcommand → draft
    known = {"draft", "approve", "export", "-h", "--help"}
    if not argv or argv[0] not in known and not argv[0].startswith("-"):
        # e.g. python src/main.py --repo cli/cli
        argv = ["draft", *argv]
    elif not argv or (
        argv
        and argv[0].startswith("-")
        and argv[0] not in {"-h", "--help"}
    ):
        argv = ["draft", *argv]

    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
