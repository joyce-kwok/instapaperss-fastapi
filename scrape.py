import requests
from bs4 import BeautifulSoup
from datetime import datetime
from email.utils import format_datetime
from xml.sax.saxutils import escape

BASE_URL = "https://www.sanrio.co.jp"
LIST_URL = "https://www.sanrio.co.jp/news/?chara=2454&pg=1"
# change pg=N or loop over pages if you want more items

# change pg=N or loop over pages if you want more items
def fetch_items(url: str):
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    items = []
    # news list wrapper; class name taken from this page’s HTML
    news_list = soup.select_one(".news-list")  # ul or div that wraps the list [page:1]
    if not news_list:
        return items

    for li in news_list.select("li"):
        a = li.select_one("a")
        if not a:
            continue

        title = a.get_text(strip=True)
        href = a.get("href")
        link = href if href.startswith("http") else BASE_URL + href

        # date
        date_el = li.select_one(".news-date")  # span with date text like 2026/01/09 [page:1]
        date_str = date_el.get_text(strip=True) if date_el else None
        pub_date = None
        if date_str:
            dt = datetime.strptime(date_str, "%Y/%m/%d")
            pub_date = format_datetime(dt)  # RFC822-style string

        # category (first label)
        cat_el = li.select_one(".news-label")  # e.g. キャンペーン / デジタル etc. [page:1]
        category = cat_el.get_text(strip=True) if cat_el else ""

        items.append(
            {
                "title": title,
                "link": link,
                "pubDate": pub_date,
                "category": category,
            }
        )

    return items



def build_rss(items):
    channel_title = "サンリオニュース - ぐでたま"
    channel_link = "https://www.sanrio.co.jp/news/?chara=2454"
    channel_desc = "サンリオ公式サイトのぐでたま関連ニュースRSSフィード（非公式）"

    parts = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    parts.append('<rss version="2.0">')
    parts.append("<channel>")
    parts.append(f"<title>{escape(channel_title)}</title>")
    parts.append(f"<link>{channel_link}</link>")
    parts.append(f"<description>{escape(channel_desc)}</description>")
    parts.append("<language>ja</language>")

    for it in items:
        parts.append("<item>")
        parts.append(f"<title><![CDATA[{it['title']}]]></title>")
        parts.append(f"<link>{it['link']}</link>")
        parts.append(f"<guid isPermaLink=\"true\">{it['link']}</guid>")
        if it["pubDate"]:
            parts.append(f"<pubDate>{it['pubDate']}</pubDate>")
        if it["category"]:
            parts.append(f"<category><![CDATA[{it['category']}]]></category>")
        parts.append("<description><![CDATA[]]></description>")
        parts.append("</item>")

    parts.append("</channel>")
    parts.append("</rss>")

    return "\n".join(parts)

