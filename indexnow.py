"""Tell IndexNow which pages changed.

Bing (and Yandex, Naver, Seznam, which share the endpoint) will fetch a changed
page within minutes of a submission instead of waiting for its own crawl. A
sitemap is the catalogue; this is the change feed, and Bing asks for both.

The URL list comes from the published sitemap rather than a list kept here, so
a page that post-render decided to withhold, a noindex page or a retired
address, is never announced. One source of truth, and it is the one the site
actually publishes.

Run after `quarto publish`, not after `quarto render`: submitting a URL whose
new content is not live yet asks Bing to come and read the old one.

    python indexnow.py            # every indexable page
    python indexnow.py URL ...    # only these
"""
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

KEY = "bfe9b1f5d8eb425ea297b7c2447647b4"
HOST = "furkanbekdemir.com"
ENDPOINT = "https://api.indexnow.org/indexnow"

# Bing's documented replies. 202 is the one that matters on a first run: the
# submission is queued while the key file is verified.
MEANING = {
    200: "kabul edildi",
    202: "kabul edildi, anahtar dogrulamasi bekliyor",
    400: "gecersiz istek",
    403: "anahtar reddedildi (dosya erisilemiyor ya da eslesmiyor)",
    422: "adresler bu alan adina ait degil",
    429: "cok fazla istek",
}


def urls_from_sitemap() -> list[str]:
    sitemap = Path(__file__).parent / "_site" / "sitemap.xml"
    if not sitemap.exists():
        sys.exit("sitemap.xml yok; once `quarto render` calistir")
    return re.findall(r"<loc>([^<]+)</loc>", sitemap.read_text(encoding="utf-8"))


def submit(urls: list[str]) -> int:
    payload = json.dumps({
        "host": HOST,
        "key": KEY,
        "keyLocation": f"https://{HOST}/{KEY}.txt",
        "urlList": urls,
    }).encode("utf-8")

    req = urllib.request.Request(
        ENDPOINT, data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    print(f"IndexNow: HTTP {code} — {MEANING.get(code, 'bilinmeyen yanit')}")
    return 0 if code in (200, 202) else 1


if __name__ == "__main__":
    urls = sys.argv[1:] or urls_from_sitemap()
    wrong = [u for u in urls if not u.startswith(f"https://{HOST}/")]
    if wrong:
        sys.exit(f"bu alan adina ait olmayan adres: {wrong[0]}")
    print(f"{len(urls)} adres bildiriliyor")
    for u in urls:
        print(f"  {u}")
    sys.exit(submit(urls))
