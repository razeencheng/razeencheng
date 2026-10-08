#!/usr/bin/env python3
"""Update only the latest-writing section, using the blog's public RSS feed."""

from datetime import timezone
from email.utils import parsedate_to_datetime
from html import escape, unescape
from pathlib import Path
import re
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


FEED_URL = "https://razeen.me/index.xml"
README_PATH = Path(__file__).resolve().parents[2] / "README.md"
START = "<!-- BLOG-POST-LIST:START -->"
END = "<!-- BLOG-POST-LIST:END -->"
POST_COUNT = 3
MAX_FEED_BYTES = 2 * 1024 * 1024


def fetch_feed():
    request = Request(FEED_URL, headers={"User-Agent": "razeencheng-profile/1.0"})
    with urlopen(request, timeout=30) as response:
        data = response.read(MAX_FEED_BYTES + 1)
    if len(data) > MAX_FEED_BYTES:
        raise ValueError("RSS feed is unexpectedly large; README was not changed.")
    return data


def latest_posts(data):
    posts = []
    for item in ET.fromstring(data).findall("./channel/item"):
        title = " ".join(unescape(item.findtext("title", "")).split())
        url = item.findtext("link", "").strip()
        parts = urlsplit(url)
        if not title or parts.scheme != "https" or parts.netloc != "razeen.me":
            continue
        if not parts.path.startswith("/posts/"):
            continue
        try:
            published = parsedate_to_datetime(item.findtext("pubDate", ""))
        except (TypeError, ValueError):
            continue
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        posts.append((published, title, url))

    # Sort by publication time, keeping each date in the feed's own time zone.
    posts.sort(key=lambda post: post[0], reverse=True)
    selected, seen = [], set()
    for published, title, url in posts:
        if url in seen:
            continue
        seen.add(url)
        title = re.sub(r"([\\`*_\[\]])", r"\\\1", escape(title, quote=False))
        url = quote(url, safe="/:?#=&%+~")
        selected.append(f"- `{published.date().isoformat()}` &nbsp; [{title}]({url})")
        if len(selected) == POST_COUNT:
            return "\n".join(selected)
    raise ValueError("RSS has fewer than three valid posts; README was not changed.")


def replace_posts(readme, posts):
    if readme.count(START) != 1 or readme.count(END) != 1:
        raise ValueError("README must contain exactly one pair of blog markers.")
    start = readme.index(START) + len(START)
    end = readme.index(END)
    if start > end:
        raise ValueError("README blog markers are in the wrong order.")
    return readme[:start] + "\n" + posts + "\n" + readme[end:]


def main():
    original = README_PATH.read_text(encoding="utf-8")
    updated = replace_posts(original, latest_posts(fetch_feed()))
    if updated == original:
        print("Latest writing is already up to date.")
        return
    README_PATH.write_text(updated, encoding="utf-8")
    print("Updated the three latest blog posts.")


if __name__ == "__main__":
    main()
