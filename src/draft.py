"""Draft customer release notes and social blurbs (template or OpenAI)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from fetch import Release


@dataclass
class DraftBundle:
    release_notes: str
    social: str
    mode: str  # "openai" | "template"


def draft_for_release(
    release: Release,
    *,
    product_name: str,
    tone: str,
    openai_model: str = "gpt-4o-mini",
) -> DraftBundle:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if api_key:
        try:
            return _openai_draft(
                release,
                product_name=product_name,
                tone=tone,
                model=openai_model,
                api_key=api_key,
            )
        except Exception as exc:  # noqa: BLE001 — fall back for free demo
            template = _template_draft(release, product_name=product_name, tone=tone)
            notice = (
                f"_Note: OpenAI rewrite failed ({exc}); fell back to template._\n\n"
            )
            return DraftBundle(
                release_notes=notice + template.release_notes,
                social=template.social,
                mode="template",
            )
    return _template_draft(release, product_name=product_name, tone=tone)


def _template_draft(
    release: Release,
    *,
    product_name: str,
    tone: str,
) -> DraftBundle:
    bullets = [b for b in _extract_bullets(release.body) if not _is_noise_bullet(b)]
    if not bullets:
        bullets = [
            "Maintenance and quality improvements under the hood.",
            "See the full release for technical details.",
        ]

    date_line = release.published_at[:10] if release.published_at else "unreleased"
    pre = " (pre-release)" if release.prerelease else ""

    notes_lines = [
        f"# {product_name} {release.tag}{pre}",
        "",
        f"**Published:** {date_line}",
        f"**Source:** [{release.name}]({release.html_url})",
        "",
        "## What's new for you",
        "",
    ]
    for b in bullets[:12]:
        notes_lines.append(f"- {b}")
    notes_lines.extend(
        [
            "",
            "## Why it matters",
            "",
            f"This update keeps {product_name} smoother and more reliable "
            f"for day-to-day work. Tone target: {tone}.",
            "",
            "---",
            "",
            "_Draft only — run `python src/main.py approve --yes` then "
            "`export`. No Discord/email API send._",
            "",
        ]
    )

    highlight = bullets[0]
    twitter = (
        f"{product_name} {release.tag} is out{pre}. "
        f"{highlight} "
        f"Details: {release.html_url}"
    )
    linkedin = (
        f"We've shipped {product_name} {release.tag}{pre}.\n\n"
        f"Highlights:\n"
        + "\n".join(f"• {b}" for b in bullets[:5])
        + f"\n\nFull notes: {release.html_url}\n\n"
        f"#ReleaseNotes #ProductUpdate"
    )

    social = "\n".join(
        [
            f"# Social drafts — {product_name} {release.tag}",
            "",
            "## X / Twitter",
            "",
            twitter[:280],
            "",
            "## LinkedIn",
            "",
            linkedin,
            "",
            "---",
            "",
            "_Draft only — approve, then export Discord/email paste snippets._",
            "",
        ]
    )
    return DraftBundle(release_notes="\n".join(notes_lines), social=social, mode="template")


def _openai_draft(
    release: Release,
    *,
    product_name: str,
    tone: str,
    model: str,
    api_key: str,
) -> DraftBundle:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    prompt = f"""You rewrite GitHub release notes for end users.

Product: {product_name}
Tone: {tone}
Tag: {release.tag}
Title: {release.name}
URL: {release.html_url}
Prerelease: {release.prerelease}

Raw release body:
---
{release.body[:8000] or "(empty body)"}
---

Return exactly two Markdown sections separated by a line containing only <<<SOCIAL>>>:

1) Customer-facing release notes: title, short intro, bullet list of user benefits
   (no internal jargon; do not invent features not in the body).
2) Social blurbs: ## X / Twitter (≤280 chars) and ## LinkedIn (short post).

Do not add Discord, email, or auto-publish instructions.
"""
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You write accurate, benefit-first product release copy.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
    )
    text = (completion.choices[0].message.content or "").strip()
    if "<<<SOCIAL>>>" in text:
        notes, social = text.split("<<<SOCIAL>>>", 1)
    else:
        notes, social = text, _template_draft(
            release, product_name=product_name, tone=tone
        ).social
    return DraftBundle(
        release_notes=notes.strip() + "\n",
        social=social.strip() + "\n",
        mode="openai",
    )


def _extract_bullets(body: str) -> list[str]:
    bullets: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if re.match(r"^[-*+]\s+", stripped) or re.match(r"^\d+\.\s+", stripped):
            item = re.sub(r"^([-*+]|\d+\.)\s+", "", stripped)
            item = _humanize(item)
            if item:
                bullets.append(item)
    if bullets:
        return bullets

    # Fallback: non-empty paragraphs / headings as rough items
    for block in re.split(r"\n\s*\n", body):
        block = block.strip()
        if not block or block.startswith("#"):
            # Keep heading text without hashes as a soft bullet
            heading = re.sub(r"^#+\s*", "", block).strip()
            if heading and not heading.lower().startswith("what's changed"):
                bullets.append(_humanize(heading.split("\n", 1)[0]))
            continue
        first = block.split("\n", 1)[0].strip()
        if first:
            bullets.append(_humanize(first))
    return bullets[:12]


def _humanize(text: str) -> str:
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Soften common eng phrasing without breaking grammar
    text = re.sub(r"^(Fix|Fixed)\b", "We fixed", text, flags=re.I)
    text = re.sub(r"^(Add|Added)\s+a\b", "New:", text, flags=re.I)
    text = re.sub(r"^(Add|Added)\b", "New:", text, flags=re.I)
    text = re.sub(r"^(Improve|Improved)\b", "We improved", text, flags=re.I)
    if text and not text.endswith((".", "!", "?")):
        text += "."
    return text


def _is_noise_bullet(text: str) -> bool:
    lowered = text.lower()
    noise_markers = (
        "chore(deps)",
        "dependabot",
        "bump the ",
        "bump nodeselector",
        "bump charm.land",
    )
    return any(m in lowered for m in noise_markers)
