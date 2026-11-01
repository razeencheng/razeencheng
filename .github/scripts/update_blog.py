#!/usr/bin/env python3
"""Refresh the latest-writing section from the English and Chinese RSS feeds.

Each row uses the English title and links to razeencheng.com. When the Chinese
blog has the same post slug, the row also links to that Chinese version.
"""

from datetime import timezone
from email.utils import parsedate_to_datetime
from html import escape, unescape
from pathlib import Path
import re
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


EN_FEED = "https://razeencheng.com/index.xml"
ZH_FEED = "https://razeen.me/index.xml"
README_PATH = Path(__file__).resolve().parents[2] / "README.md"
START = "<!-- BLOG-POST-LIST:START -->"
END = "<!-- BLOG-POST-LIST:END -->"
POST_COUNT = 3
MAX_FEED_BYTES = 2 * 1024 * 1024
EN_HOST = "razeencheng.com"
ZH_HOST = "razeen.me"
EN_PREFIX = "/posts/en/"
ZH_PREFIX = "/posts/"


def fetch_feed(url):
    request = Request(url, headers={"User-Agent": "razeencheng-profile/1.0"})
    with urlopen(request, timeout=30) as response:
        data = response.read(MAX_FEED_BYTES + 1)
    if len(data) > MAX_FEED_BYTES:
        raise ValueError(f"RSS feed {url} is unexpectedly large; README was not changed.")
    return data


def post_slug(path, prefix):
    if not path.startswith(prefix):
        return None
    slug = path[len(prefix):].strip("/")
    if not slug or "/" in slug:
        return None
    return slug


def parse_posts(data, host, prefix):
    posts = []
    for item in ET.fromstring(data).findall("./channel/item"):
        title = " ".join(unescape(item.findtext("title", "")).split())
        url = item.findtext("link", "").strip()
        parts = urlsplit(url)
        slug = post_slug(parts.path, prefix)
        if not title or parts.scheme != "https" or parts.netloc != host or slug is None:
            continue
        try:
            published = parsedate_to_datetime(item.findtext("pubDate", ""))
        except (TypeError, ValueError):
            continue
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        posts.append((published, title, url, slug))

    posts.sort(key=lambda post: post[0], reverse=True)
    selected, seen = [], set()
    for post in posts:
        if post[3] in seen:
            continue
        seen.add(post[3])
        selected.append(post)
    return selected


def markdown_title(title):
    return re.sub(r"([\\`*_\[\]])", r"\\\1", escape(title, quote=False))


def markdown_url(url):
    return quote(url, safe="/:?#=&%+~")


def render_posts(english_posts, chinese_posts):
    chinese_by_slug = {slug: url for _, _, url, slug in chinese_posts}
    lines = []
    for published, title, url, slug in english_posts:
        line = f"- `{published.date().isoformat()}` &nbsp; [{markdown_title(title)}]({markdown_url(url)})"
        chinese_url = chinese_by_slug.get(slug)
        if chinese_url:
            line += f" · [中文]({markdown_url(chinese_url)})"
        lines.append(line)
        if len(lines) == POST_COUNT:
            return "\n".join(lines)
    raise ValueError("English RSS has fewer than three valid posts; README was not changed.")


def replace_posts(readme, posts):
    if readme.count(START) != 1 or readme.count(END) != 1:
        raise ValueError("README must contain exactly one pair of blog markers.")
    start = readme.index(START) + len(START)
    end = readme.index(END)
    if start > end:
        raise ValueError("README blog markers are in the wrong order.")
    return readme[:start] + "\n" + posts + "\n" + readme[end:]


def main():
    posts = render_posts(
        parse_posts(fetch_feed(EN_FEED), EN_HOST, EN_PREFIX),
        parse_posts(fetch_feed(ZH_FEED), ZH_HOST, ZH_PREFIX),
    )
    original = README_PATH.read_text(encoding="utf-8")
    updated = replace_posts(original, posts)
    if updated == original:
        print("Latest writing is already up to date.")
        return
    README_PATH.write_text(updated, encoding="utf-8")
    print("Updated the three latest blog posts.")


if __name__ == "__main__":
    main()
