"""Build a free local export pack (Markdown + mailto + Discord paste)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from approve import REQUIRED_ARTIFACTS, verify_approval

EXPORT_DIRNAME = "export"


def _extract_title(release_notes: str) -> str:
    for line in release_notes.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return re.sub(r"^#+\s*", "", stripped).strip()
    return "Release notes"


def _section(social: str, heading: str) -> str:
    """Return body under `## heading` until the next `##` or EOF."""
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(social)
    if not match:
        return ""
    rest = social[match.end() :]
    next_heading = re.search(r"^##\s+", rest, re.MULTILINE)
    body = rest[: next_heading.start()] if next_heading else rest
    # Drop trailing draft footer
    body = re.split(r"^---\s*$", body, maxsplit=1, flags=re.MULTILINE)[0]
    return body.strip()


def _mailto_url(*, to: str, subject: str, body: str) -> str:
    query_parts = [f"subject={quote(subject, safe='')}"]
    if body:
        query_parts.append(f"body={quote(body, safe='')}")
    query = "&".join(query_parts)
    recipient = to.strip()
    return f"mailto:{recipient}?{query}" if recipient else f"mailto:?{query}"


def build_export_pack(
    out_dir: Path,
    *,
    mailto_to: str = "",
    email_subject: str = "",
    dry_run: bool = False,
) -> Path:
    """Write out/export/ after verifying human approval. Never sends via API."""
    approval = verify_approval(out_dir)
    export_dir = out_dir / EXPORT_DIRNAME

    notes = (out_dir / "release-notes.md").read_text(encoding="utf-8")
    social = (out_dir / "social.md").read_text(encoding="utf-8")
    title = _extract_title(notes)
    subject = email_subject.strip() or f"[Draft] {title}"

    twitter = _section(social, "X / Twitter") or _section(social, "Twitter")
    linkedin = _section(social, "LinkedIn")

    email_body = "\n".join(
        [
            f"Subject: {subject}",
            "",
            notes.strip(),
            "",
            "---",
            "",
            "Social blurbs (optional):",
            "",
            social.strip(),
            "",
        ]
    )

    mailto = _mailto_url(to=mailto_to, subject=subject, body=notes.strip())

    discord_paste = "\n".join(
        [
            f"# Discord paste pack — {title}",
            "",
            "_Copy one block at a time into Discord. No bot/webhook send._",
            "",
            "## Channel message — release notes",
            "",
            "```",
            notes.strip(),
            "```",
            "",
            "## Channel message — X / Twitter blurb",
            "",
            "```",
            (twitter or "(edit out/social.md)").strip(),
            "```",
            "",
            "## Channel message — LinkedIn blurb",
            "",
            "```",
            (linkedin or "(edit out/social.md)").strip(),
            "```",
            "",
            "## Short announce (combined)",
            "",
            "```",
            f"**{title}**",
            "",
            (twitter or (notes.splitlines()[0] if notes else title)).strip(),
            "```",
            "",
        ]
    )

    readme = "\n".join(
        [
            "# Export pack",
            "",
            "Human-approved local artifacts. **Nothing was sent.**",
            "",
            "| File | Use |",
            "|------|-----|",
            "| `release-notes.md` | Paste into changelog / docs / GitHub release |",
            "| `social.md` | Full social draft source |",
            "| `email-body.md` | Paste into any email client |",
            "| `mailto.url` | Open in a browser/mail client (draft only) |",
            "| `discord-paste.md` | Copy/paste into Discord channels |",
            "| `manifest.json` | Approval + export metadata |",
            "",
            "Re-export after edits: approve again, then `python src/main.py export`.",
            "",
        ]
    )

    manifest = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "approved_at": approval.get("approved_at"),
        "dry_run": dry_run,
        "mailto_to": mailto_to or None,
        "email_subject": subject,
        "files": list(REQUIRED_ARTIFACTS)
        + [
            "email-body.md",
            "mailto.url",
            "discord-paste.md",
            "README.md",
            "manifest.json",
        ],
        "send": {
            "discord_api": False,
            "email_api": False,
            "mode": "local-paste-and-mailto-only",
        },
    }

    planned = {
        "README.md": readme,
        "release-notes.md": notes if notes.endswith("\n") else notes + "\n",
        "social.md": social if social.endswith("\n") else social + "\n",
        "email-body.md": email_body if email_body.endswith("\n") else email_body + "\n",
        "mailto.url": mailto + "\n",
        "discord-paste.md": discord_paste if discord_paste.endswith("\n") else discord_paste + "\n",
        "manifest.json": json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    }

    if dry_run:
        print(f"[dry-run] Would write {len(planned)} files under {export_dir}/")
        for name in planned:
            print(f"  - {export_dir / name}")
        print(f"[dry-run] mailto: {mailto[:120]}{'…' if len(mailto) > 120 else ''}")
        return export_dir

    export_dir.mkdir(parents=True, exist_ok=True)
    for name, content in planned.items():
        (export_dir / name).write_text(content, encoding="utf-8")

    print(f"Export pack written to {export_dir}/")
    for name in planned:
        print(f"  - {export_dir / name}")
    print("No Discord/email API send — paste or open mailto.url yourself.")
    return export_dir
