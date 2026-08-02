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
# A hash of every rendered page, written by post-render. The sitemap will not do
# as a signal: edit a page without adding an address and it comes out
# byte-identical, so an unfinished deploy would read as a finished one.
BUILD_ID = "https://furkanbekdemir.com/build-id.txt"
TIMEOUT_S = 600
POLL_S = 10


def run(cmd: list[str]) -> None:
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=ROOT, check=True)


def live_build_id() -> str | None:
    # A cache-buster, because the CDN will happily serve the previous copy for
    # its full max-age and we would read that as "deploy finished".
    url = f"{BUILD_ID}?cb={int(time.time())}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return r.read().decode("utf-8").strip()
    except (urllib.error.URLError, TimeoutError):
        return None


def wait_for_deploy(expected: str) -> bool:
    print(f"dagitim bekleniyor, build id {expected} (en fazla {TIMEOUT_S // 60} dk)")
    started = time.time()
    while time.time() - started < TIMEOUT_S:
        live = live_build_id()
        if live == expected:
            print(f"  dagitim tamamlandi ({int(time.time() - started)} saniye)")
            return True
        time.sleep(POLL_S)
    print(f"  ZAMAN ASIMI: canlida hala {live_build_id()}, bildirim atlaniyor")
    return False


def main() -> int:
    run(["quarto", "render"])

    stamp_file = ROOT / "_site" / "build-id.txt"
    if not stamp_file.exists():
        sys.exit("build-id.txt uretilmedi; post-render calisti mi?")
    expected = stamp_file.read_text(encoding="utf-8").strip()

    run(["quarto", "publish", "gh-pages", "--no-prompt", "--no-render"])

    if not wait_for_deploy(expected):
        print("indexnow.py'yi dagitim tamamlaninca elle calistir")
        return 1
    run([sys.executable, str(ROOT / "indexnow.py")])
    return 0


if __name__ == "__main__":
    sys.exit(main())
