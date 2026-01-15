import requests
from bs4 import BeautifulSoup
from datetime import datetime
from email.utils import format_datetime
# change pg=N or loop over pages if you want more items
def fetch_items_from_sanrio_news(url: str):
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
