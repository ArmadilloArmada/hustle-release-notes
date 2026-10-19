# hustle-release-notes

Turn raw GitHub releases into **customer-facing changelog copy** and **social blurbs** for indie apps.

Part of [Project Hustle](https://github.com/armadilloarmada) Tier 0 — changelog / release-note rewriter. Draft → **human approve** → **free local export** (Markdown + mailto + Discord paste). **No Discord or email API send.**

## What it does

1. Watches a public repo via the **GitHub Releases API** (default: `cli/cli`)
2. Rewrites the latest release body into friendly release notes + X/LinkedIn drafts
3. Writes artifacts to `out/` for you to edit
4. Records an explicit human approval (`out/approval.json`)
5. Exports a paste-ready pack under `out/export/` (mailto URL + Discord snippets)

Optional `OPENAI_API_KEY` upgrades the rewrite. Without a key, a deterministic **template rewrite** still runs (free demo).

## Requirements

- Python 3.11+
- Network access to `api.github.com` (draft step only)
- Optional: `OPENAI_API_KEY` for LLM rewrite
- Optional: `GITHUB_TOKEN` / `GH_TOKEN` for a higher GitHub API rate limit (unauthenticated works; ~60 req/hr shared)

## Setup

```bash
git clone https://github.com/armadilloarmada/hustle-release-notes.git
cd hustle-release-notes
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml   # already present for first run
```

## Config

Edit `config.yaml`:

| Key | Default | Purpose |
|-----|---------|---------|
| `repo` | `cli/cli` | `owner/name` to watch |
| `release_limit` | `1` | How many releases to fetch |
| `product_name` | `GitHub CLI` | Brand name in copy |
| `tone` | friendly… | Voice hints |
| `openai_model` | `gpt-4o-mini` | Used only when `OPENAI_API_KEY` is set |
| `export.mailto_to` | `""` | Optional recipient baked into `mailto.url` |
| `export.email_subject` | `""` | Optional subject; defaults to draft title |

## Run

```bash
# 1) Draft (also the default if you omit the subcommand)
python src/main.py draft
# or override the watched repo:
python src/main.py draft --repo cli/cli --limit 1
python src/main.py --repo cli/cli

# 2) Human approve (required before export)
python src/main.py approve --yes

# 3) Free export pack (local files only)
python src/main.py export --dry-run
python src/main.py export
python src/main.py export --mailto-to you@example.com --print-mailto
```

### Outputs

| Path | Contents |
|------|----------|
| `out/release-notes.md` | Customer-facing release notes draft |
| `out/social.md` | X/Twitter + LinkedIn blurbs |
| `out/approval.json` | Human approval stamp (content hashes) |
| `out/export/release-notes.md` | Approved notes copy |
| `out/export/social.md` | Approved social copy |
| `out/export/email-body.md` | Paste-ready email body |
| `out/export/mailto.url` | Draft-only `mailto:` link |
| `out/export/discord-paste.md` | Discord copy/paste blocks |
| `out/export/README.md` | Pack usage |
| `out/export/manifest.json` | Metadata (confirms no API send) |

Editing drafts after approve invalidates the stamp — run `approve` again before `export`.

## Compliance notes

- Uses only the **public GitHub Releases API** — no private repo scraping in v1
- Respect rate limits; prefer a token if you poll often
- Do not invent features: LLM/template drafts are grounded in the release body — still **human-review** before shipping
- Export is **offline paste / mailto only** — no Discord webhooks, bots, or email ESP/API
- Risk: wrong repo access could surface unreleased wording — stick to public releases you intend to announce

## License

MIT
