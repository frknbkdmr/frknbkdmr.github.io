"""Post-render fixups Quarto does not do itself.

1. Inject <link rel="canonical"> into every page. Quarto knows site-url but
   emits no canonical tag, which leaves "/", "/index.html" and any query-string
   variant looking like separate pages to a crawler.
2. Point the sitemap at the bare origin rather than /index.html, and drop the
   duplicate that rewrite creates, so one form is authoritative everywhere.
3. Defer the classic scripts Quarto puts in <head>. They are parser-blocking
   where nothing on these pages needs them before first paint.
4. Delete the search index when search is switched off, so a dead file is not
   published.

The site URL is read from _quarto.yml rather than repeated here: a second copy
of a value nobody remembers to update is a silent wrong-domain canonical.

Idempotent: re-running over an already-processed _site changes nothing.
Exits non-zero if a page could not be given a canonical, so a broken build
fails loudly instead of publishing quietly incomplete pages.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "_site"
CONFIG = ROOT / "_quarto.yml"


def site_url() -> str:
    """Read website.site-url from _quarto.yml without a YAML dependency."""
    text = CONFIG.read_text(encoding="utf-8")
    m = re.search(r'^\s*site-url:\s*["\']?([^"\'\s#]+)', text, re.M)
    if not m:
        sys.exit(f"site-url not found in {CONFIG.name}; cannot build canonical URLs")
    return m.group(1).rstrip("/")


def search_enabled() -> bool:
    text = CONFIG.read_text(encoding="utf-8")
    return not re.search(r"^\s*search:\s*false\b", text, re.M)


def canonical_for(html_path: Path, base: str) -> str:
    rel = html_path.relative_to(OUT).as_posix()
    return f"{base}/" if rel == "index.html" else f"{base}/{rel}"


def inject_canonical(path: Path, base: str) -> bool | None:
    """True if changed, False if already correct, None if it could not be done."""
    text = path.read_text(encoding="utf-8")
    tag = f'<link rel="canonical" href="{canonical_for(path, base)}">'

    existing = re.search(r'<link\s+rel="canonical"[^>]*>', text, re.I)
    if existing:
        if existing.group(0) == tag:
            return False
        text = text[: existing.start()] + tag + text[existing.end():]
    else:
        m = re.search(r"</head>", text, re.I)
        if not m:
            return None
        text = text[: m.start()] + tag + "\n" + text[m.start():]

    path.write_text(text, encoding="utf-8")
    return True


def defer_head_scripts(path: Path) -> int:
    """Add defer to classic <script src> tags. Modules already defer; anything
    already marked defer/async is left alone."""
    text = path.read_text(encoding="utf-8")
    head_end = text.lower().find("</head>")
    if head_end == -1:
        return 0

    head, rest = text[:head_end], text[head_end:]
    # Skip anything already deferred/async, and module scripts, which defer by
    # default and where the attribute would be inert noise.
    pattern = re.compile(
        r"<script\b(?![^>]*\b(?:defer|async)\b)(?![^>]*\btype\s*=)([^>]*\bsrc=)", re.I
    )
    head, n = pattern.subn(r"<script defer\1", head)
    if n:
        path.write_text(head + rest, encoding="utf-8")
    return n


def normalise_sitemap(base: str) -> bool:
    sm = OUT / "sitemap.xml"
    if not sm.exists():
        return False
    text = sm.read_text(encoding="utf-8")
    fixed = text.replace(f"{base}/index.html", f"{base}/")

    # Rewriting index.html to "/" can collide with an entry Quarto already
    # emitted for the bare origin; keep the first of each <loc>.
    seen, kept = set(), []
    for block in re.findall(r"[ \t]*<url>.*?</url>\n?", fixed, re.S):
        loc = re.search(r"<loc>(.*?)</loc>", block, re.S)
        if loc and loc.group(1) in seen:
            continue
        if loc:
            seen.add(loc.group(1))
        kept.append(block)

    rebuilt = re.sub(r"[ \t]*<url>.*</url>\n?", "".join(kept), fixed, flags=re.S)
    if rebuilt == text:
        return False
    sm.write_text(rebuilt, encoding="utf-8")
    return True


def main() -> None:
    if not OUT.is_dir():
        sys.exit(f"output dir not found: {OUT}")

    base = site_url()
    pages = sorted(OUT.glob("*.html"))
    changed, failed, deferred = [], [], 0

    for p in pages:
        result = inject_canonical(p, base)
        if result is None:
            failed.append(p.name)
        elif result:
            changed.append(p.name)
        deferred += defer_head_scripts(p)

    print(f"canonical: {len(changed)}/{len(pages)} page(s) updated"
          + (f" ({', '.join(changed)})" if changed else ""))
    if deferred:
        print(f"defer: {deferred} script tag(s)")
    if normalise_sitemap(base):
        print("sitemap: index.html -> /, duplicates dropped")

    index = OUT / "search.json"
    if index.exists() and not search_enabled():
        index.unlink()
        print("search.json: removed (search disabled)")

    if failed:
        sys.exit("no </head> in: " + ", ".join(failed))


if __name__ == "__main__":
    main()
