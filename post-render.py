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
import os
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
    """Extensionless URLs, because they outlive the generator that made them.
    Once ORCID or a paper cites furkanbekdemir.com/research, that address can
    never move — and it must not depend on the pages still being .html."""
    rel = html_path.relative_to(OUT).as_posix()
    if rel.endswith("/index.html"):
        rel = rel[: -len("index.html")]          # research/index.html -> research/
    elif rel == "index.html":
        rel = ""
    else:
        rel = rel[: -len(".html")]               # research/cv.html -> research/cv
    return f"{base}/{rel}"


def is_doorway(text: str) -> bool:
    """The root redirect page ships its own canonical and asks not to be
    indexed; rewriting it would point crawlers back at the doorway."""
    return bool(re.search(r'<meta[^>]+name="robots"[^>]+noindex', text, re.I))


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


SKIP_TEXT = {"tr": "Ana içeriğe geç", "en": "Skip to main content"}


def fix_a11y(path: Path) -> list[str]:
    """Repairs on Quarto's own navbar/footer markup that cannot be reached from
    source: a bogus ARIA role, a missing bypass link, and unmarked English
    chrome on the Turkish page."""
    text = path.read_text(encoding="utf-8")
    original, done = text, []

    # Quarto puts role="menu" on the hamburger <button>. It is a button, and the
    # explicit role overrides that in the accessibility tree (WCAG 4.1.2).
    text, n = re.subn(r'(<button[^>]*class="navbar-toggler"[^>]*?)\s+role="menu"',
                      r"\1", text)
    if n:
        done.append("navbar role")

    # WCAG 2.4.1: let keyboard users jump the repeated navigation.
    if "quarto-skip-link" not in text:
        lang = re.search(r'<html[^>]*\blang="([a-z-]+)"', text)
        label = SKIP_TEXT.get((lang.group(1) if lang else "en")[:2], SKIP_TEXT["en"])
        m = re.search(r"<body[^>]*>", text)
        if m:
            link = (f'\n<a href="#quarto-document-content" class="quarto-skip-link">'
                    f"{label}</a>")
            text = text[: m.end()] + link + text[m.end():]
            done.append("skip link")

    # WCAG 3.1.2: the Turkish page keeps an English navbar and footer.
    if re.search(r'<html[^>]*\blang="tr"', text):
        # Insert the attribute after the tag name. Splicing it into the class
        # attribute instead silently eats a class name.
        text, a = re.subn(r'(<nav\b)(?![^>]*\blang=)([^>]*\bclass="[^"]*navbar)',
                          r'\1 lang="en"\2', text, count=1)
        text, b = re.subn(r'(<footer\b)(?![^>]*\blang=)([^>]*\bclass="[^"]*footer)',
                          r'\1 lang="en"\2', text, count=1)
        if a or b:
            done.append("lang parts")

    if text != original:
        path.write_text(text, encoding="utf-8")
    return done


def point_brand_at_home(path: Path) -> bool:
    """Quarto aims the navbar brand at the site root, which here is the
    redirect doorway — every page would link readers into a bounce. Aim it at
    the section index instead."""
    home = OUT / "research" / "index.html"
    if not home.exists():
        return False
    rel = os.path.relpath(home, path.parent).replace(os.sep, "/")
    text = path.read_text(encoding="utf-8")
    fixed, n = re.subn(r'(<a\b[^>]*\bclass="[^"]*navbar-brand[^"]*"[^>]*\bhref=")[^"]*(")',
                       rf"\1{rel}\2", text)
    if n:
        path.write_text(fixed, encoding="utf-8")
    return bool(n)


def scope_jsonld(path: Path) -> bool:
    """head.html is global, so its ProfilePage schema lands on every page.
    Only the homepage is a profile; the rest are ordinary pages about it."""
    if path.name == "index.html":
        return False
    text = path.read_text(encoding="utf-8")
    fixed = text.replace('"@type": "ProfilePage"', '"@type": "WebPage"', 1)
    fixed = fixed.replace('"mainEntity": {', '"about": {', 1)
    if fixed == text:
        return False
    path.write_text(fixed, encoding="utf-8")
    return True


def normalise_sitemap(base: str) -> bool:
    sm = OUT / "sitemap.xml"
    if not sm.exists():
        return False
    text = sm.read_text(encoding="utf-8")
    # Match the extensionless form the canonical tags declare, or the sitemap
    # would advertise a second address for every page.
    fixed = re.sub(r"(<loc>[^<]*?)/index\.html(</loc>)", r"\1/\2", text)
    fixed = re.sub(r"(<loc>[^<]*?)\.html(</loc>)", r"\1\2", fixed)

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
    # rglob, not glob: a page in a subdirectory needs a canonical just as much,
    # and would otherwise be skipped without a word.
    pages = sorted(p for p in OUT.rglob("*.html") if "site_libs" not in p.parts)
    changed, failed, deferred, fixes, scoped = [], [], 0, set(), 0

    for p in pages:
        if is_doorway(p.read_text(encoding="utf-8")):
            continue
        result = inject_canonical(p, base)
        if result is None:
            failed.append(p.name)
        elif result:
            changed.append(p.name)
        deferred += defer_head_scripts(p)
        fixes.update(fix_a11y(p))
        scoped += scope_jsonld(p)
        point_brand_at_home(p)

    print(f"canonical: {len(changed)}/{len(pages)} page(s) updated"
          + (f" ({', '.join(changed)})" if changed else ""))
    if deferred:
        print(f"defer: {deferred} script tag(s)")
    if fixes:
        print("a11y: " + ", ".join(sorted(fixes)))
    if scoped:
        print(f"json-ld: {scoped} page(s) narrowed to WebPage")
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
