#!/usr/bin/env python3
"""CLI: fetch GitHub releases → draft customer notes + social blurbs → out/."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml

from draft import draft_for_release
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Rewrite public GitHub releases into customer-facing notes "
            "and social blurbs (writes out/release-notes.md + out/social.md)."
        )
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Path to config YAML (default: {DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "--repo",
        help="Override config repo (owner/name), e.g. cli/cli",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Override how many recent releases to fetch (uses latest for drafts)",
    )
    args = parser.parse_args(argv)

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

    # Draft from the newest release; mention siblings if limit > 1
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

    print(f"Mode: {bundle.mode}")
    print(f"Wrote {notes_path.relative_to(ROOT)}")
    print(f"Wrote {social_path.relative_to(ROOT)}")
    print("Human approve offline — no Discord/email push in v1.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
