"""Publish the site, wait for the deploy to land, then tell IndexNow.

Use this instead of `quarto publish gh-pages`:

    python publish.py

The waiting is the point. `quarto publish` returns once gh-pages has been
pushed, but GitHub Pages takes another minute or two to serve the new files.
Submitting a URL in that window asks Bing to come and read the version that is
still live, which is the old one, and a crawler that has just been told a page
is unchanged does not hurry back.

So the deploy is confirmed before anything is announced, by comparing the
sitemap being served against the one just built. If they never match, the
submission is skipped rather than sent against stale content.
"""
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
SITEMAP = "https://furkanbekdemir.com/sitemap.xml"
TIMEOUT_S = 600
POLL_S = 10


def run(cmd: list[str]) -> None:
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=ROOT, check=True)


def live_sitemap() -> str | None:
    # A cache-buster, because the CDN will happily serve the previous copy for
    # its full max-age and we would read that as "deploy finished".
    url = f"{SITEMAP}?cb={int(time.time())}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return r.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError):
        return None


def wait_for_deploy(expected: str) -> bool:
    print(f"dagitim bekleniyor (en fazla {TIMEOUT_S // 60} dakika)")
    deadline = time.time() + TIMEOUT_S
    while time.time() < deadline:
        if live_sitemap() == expected:
            waited = int(TIMEOUT_S - (deadline - time.time()))
            print(f"  dagitim tamamlandi ({waited} saniye)")
            return True
        time.sleep(POLL_S)
    print("  ZAMAN ASIMI: yayin gorunmedi, bildirim atlaniyor")
    return False


def main() -> int:
    run(["quarto", "render"])

    built = (ROOT / "_site" / "sitemap.xml")
    if not built.exists():
        sys.exit("sitemap.xml uretilmedi")
    expected = built.read_text(encoding="utf-8")

    run(["quarto", "publish", "gh-pages", "--no-prompt", "--no-render"])

    if not wait_for_deploy(expected):
        print("indexnow.py'yi sonra elle calistir")
        return 1
    run([sys.executable, str(ROOT / "indexnow.py")])
    return 0


if __name__ == "__main__":
    sys.exit(main())
