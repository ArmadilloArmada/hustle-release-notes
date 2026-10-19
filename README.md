# hustle-release-notes

Turn raw GitHub releases into **customer-facing changelog copy** and **social blurbs** for indie apps.

Part of [Project Hustle](https://github.com/armadilloarmada) Tier 0 — changelog / release-note rewriter. v1 drafts to disk for human approval; **no Discord or email push**.

## What it does

1. Watches a public repo via the **GitHub Releases API** (default: `cli/cli`)
2. Rewrites the latest release body into friendly release notes + X/LinkedIn drafts
3. Writes artifacts to `out/` for you to edit and publish manually

Optional `OPENAI_API_KEY` upgrades the rewrite. Without a key, a deterministic **template rewrite** still runs (free demo).

## Requirements

- Python 3.11+
- Network access to `api.github.com`
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

## Run

```bash
python src/main.py
# or override the watched repo:
python src/main.py --repo cli/cli --limit 1
```

### Outputs

| Path | Contents |
|------|----------|
| `out/release-notes.md` | Customer-facing release notes draft |
| `out/social.md` | X/Twitter + LinkedIn blurbs |

## Compliance notes

- Uses only the **public GitHub Releases API** — no private repo scraping in v1
- Respect rate limits; prefer a token if you poll often
- Do not invent features: LLM/template drafts are grounded in the release body — still **human-review** before shipping
- Risk: wrong repo access could surface unreleased wording — stick to public releases you intend to announce

## License

MIT
