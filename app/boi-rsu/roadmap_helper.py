import os
import requests
from pathlib import Path

def _try_fetch_raw_github(path_candidates):
    """Try fetching raw content from several GitHub raw URLs."""
    for url in path_candidates:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200 and resp.text.strip():
                return resp.text
        except Exception:
            continue
    return None


def fetch_roadmap(topic: str) -> str:
    """Return roadmap text for a given topic by attempting several sources.

    The function first tries to fetch a raw README from the popular
    `kamranahmedse/roadmap.sh` repository on GitHub using common path
    patterns. If that fails, it fetches the public roadmap.sh page and
    returns the HTML as a fallback.
    """
    if not topic:
        return ""

    slug = topic.lower().strip().replace(" ", "-")

    raw_candidates = [
        f"https://raw.githubusercontent.com/kamranahmedse/roadmap.sh/main/roadmaps/{slug}/README.md",
        f"https://raw.githubusercontent.com/kamranahmedse/roadmap.sh/main/roadmaps/{slug}.md",
        f"https://raw.githubusercontent.com/kamranahmedse/roadmap.sh/main/roadmaps/{slug}/README.MD",
    ]

    text = _try_fetch_raw_github(raw_candidates)
    if text:
        return text

    # Fallback: try fetching the rendered roadmap.sh page
    page_candidates = [
        f"https://roadmap.sh/{slug}",
        f"https://roadmap.sh/roadmaps/{slug}",
        f"https://roadmap.sh/{slug}-roadmap",
    ]
    for url in page_candidates:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200 and resp.text.strip():
                return resp.text
        except Exception:
            continue

    return ""
