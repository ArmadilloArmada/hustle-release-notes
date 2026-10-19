"""Fetch public GitHub releases (unauthenticated, rate-limit aware)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

GITHUB_API = "https://api.github.com"
USER_AGENT = "hustle-release-notes/0.1 (+https://github.com/armadilloarmada/hustle-release-notes)"


@dataclass
class Release:
    tag: str
    name: str
    body: str
    html_url: str
    published_at: str | None
    prerelease: bool


def _parse_release(item: dict[str, Any]) -> Release:
    return Release(
        tag=item.get("tag_name") or "",
        name=item.get("name") or item.get("tag_name") or "Untitled",
        body=(item.get("body") or "").strip(),
        html_url=item.get("html_url") or "",
        published_at=item.get("published_at"),
        prerelease=bool(item.get("prerelease")),
    )


def fetch_releases(
    owner: str,
    repo: str,
    *,
    limit: int = 1,
    token: str | None = None,
) -> list[Release]:
    """Return up to `limit` recent releases for owner/repo.

    Uses the public GitHub Releases API. Unauthenticated callers share a low
    rate limit (~60/hr); we honor Retry-After / X-RateLimit-Remaining.
    """
    if limit < 1:
        raise ValueError("limit must be >= 1")

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"{GITHUB_API}/repos/{owner}/{repo}/releases"
    params = {"per_page": min(limit, 30)}

    with httpx.Client(timeout=30.0, headers=headers) as client:
        response = _get_with_rate_limit(client, url, params)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError(f"Unexpected GitHub response for {owner}/{repo}")
        return [_parse_release(item) for item in payload[:limit]]


def _get_with_rate_limit(
    client: httpx.Client,
    url: str,
    params: dict[str, Any],
    *,
    max_retries: int = 3,
) -> httpx.Response:
    for attempt in range(max_retries + 1):
        response = client.get(url, params=params)
        remaining = response.headers.get("X-RateLimit-Remaining")
        if response.status_code == 403 and remaining == "0":
            wait = _retry_wait_seconds(response)
            if attempt >= max_retries:
                raise RuntimeError(
                    "GitHub API rate limit exceeded. Wait and retry, "
                    "or set GITHUB_TOKEN for a higher quota."
                )
            time.sleep(wait)
            continue
        if response.status_code == 429:
            wait = _retry_wait_seconds(response)
            if attempt >= max_retries:
                raise RuntimeError("GitHub API returned 429 too many times.")
            time.sleep(wait)
            continue
        return response
    raise RuntimeError("GitHub request failed after retries")


def _retry_wait_seconds(response: httpx.Response) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return min(float(retry_after), 60.0)
        except ValueError:
            pass
    reset = response.headers.get("X-RateLimit-Reset")
    if reset:
        try:
            delay = int(reset) - int(time.time())
            return float(max(1, min(delay, 60)))
        except ValueError:
            pass
    return 5.0
