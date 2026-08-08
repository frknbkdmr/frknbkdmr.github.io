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
import hashlib
import json
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


def qmd_to_markdown(src: str) -> tuple[str, str, str]:
    """Strip a .qmd back to plain markdown. Returns (title, description, body).

    A static host cannot negotiate on Accept, so agents cannot ask for
    markdown, but they can fetch it from a known path. The sources are already
    markdown; what has to come off is Quarto's own syntax, and the raw HTML
    blocks, which are markup an agent gains nothing from.
    """
    m = re.match(r"^---\n(.*?)\n---\n", src, re.S)
    front, body = (m.group(1), src[m.end():]) if m else ("", src)

    def field(name):
        f = re.search(rf'^{name}:\s*&?\w*\s*["\']?(.+?)["\']?\s*$', front, re.M)
        return f.group(1).strip() if f else ""

    title = field("title") or field("pagetitle")
    desc = field("description-meta") or field("description")

    body = re.sub(r"```\{=html\}.*?```", "", body, flags=re.S)   # raw HTML blocks
    body = re.sub(r"^:::+.*$", "", body, flags=re.M)             # div fences
    body = re.sub(r"\[([^\]]+)\]\{[^}]*\}", r"\1", body)         # [text]{.class}
    body = re.sub(r"^(#+ .*?)\s*\{[^}]*\}\s*$", r"\1", body, flags=re.M)
    body = re.sub(r"&middot;", "·", body)
    body = re.sub(r"&ndash;", "–", body)
    body = re.sub(r"<[^>]+>", "", body)                          # stray tags
    # Stripping the hero <svg> leaves the whitespace that sat between its tags.
    body = re.sub(r"[ \t]+$", "", body, flags=re.M)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    # The page title and the body's own h1 are the same string on the homepage.
    if title:
        body = re.sub(rf"^#\s+{re.escape(title)}\s*\n+", "", body)
    return title, desc, body


def write_llms_txt(base: str) -> bool:
    """Publish llms.txt and llms-full.txt.

    One fetch of llms-full.txt costs an agent a few kilobytes; reading the five
    rendered pages costs a quarter of a megabyte, nearly all of it markup.
    """
    # Discovered, not listed. A hardcoded roster silently omits any page added
    # later, and the omission looks exactly like a page that has no content.
    def under(name: str) -> list[Path]:
        return sorted((ROOT / name).glob("*.qmd"),
                      key=lambda p: (p.stem != "index", p.stem))

    # Navbar order, each section index immediately before the pages under it.
    # tools.qmd is the tools index even though it sits at the root, so it is
    # named here rather than swept up by the glob.
    sources = [ROOT / "index.qmd"]
    sources += under("research")
    sources += [ROOT / "tools.qmd"] + under("tools")
    sources += under("log")
    sources += [ROOT / "cv.qmd", ROOT / "notlar.qmd"] + under("notlar")
    sources += [ROOT / "notes.qmd"] + under("notes")
    sources = [p for p in sources if p.exists()]

    pages = []
    for p in sources:
        rel = p.relative_to(ROOT).with_suffix("").as_posix()
        path = "/" if rel == "index" else (
            f"/{rel[: -len('/index')]}/" if rel.endswith("/index") else f"/{rel}")
        title, desc, body = qmd_to_markdown(p.read_text(encoding="utf-8"))
        pages.append((title or p.stem, title or p.stem, desc, path, body))

    lede = ("Psychiatry resident and computational psychiatry researcher at "
            "Ondokuz Mayıs University, Samsun. Belief updating, sensory "
            "attenuation, and instrumentation for psychiatric research.")

    idx = [f"# Furkan Bekdemir", "", f"> {lede}", "",
           f"ORCID: https://orcid.org/0000-0002-7236-5776",
           f"Code: https://github.com/frknbkdmr",
           f"Full text of every page: {base}/llms-full.txt", "", "## Pages", ""]
    for label, _title, desc, path, _body in pages:
        idx.append(f"- [{label}]({base}{path})" + (f": {desc}" if desc else ""))
    idx.append("")

    full = [f"# Furkan Bekdemir", "", f"> {lede}", "",
            f"Source: {base}  ·  ORCID: https://orcid.org/0000-0002-7236-5776",
            "", "---", ""]
    for label, title, _desc, path, body in pages:
        full += [f"# {title}", "", f"URL: {base}{path}", "", body, "", "---", ""]

    changed = False
    for name, lines in (("llms.txt", idx), ("llms-full.txt", full)):
        text = "\n".join(lines).rstrip() + "\n"
        path = OUT / name
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8", newline="\n")
            changed = True
    return changed


# Where each subdirectory's index actually lives. tools/ and log/ both belong
# under /tools, because the logs are listed there and have no index of their own;
# a trail has to point at a page that exists, not at the directory it implies.
SECTIONS = {
    "research": ("/research/", "Research"),
    "tools":    ("/tools",     "Instruments and code"),
    "log":      ("/tools",     "Instruments and code"),
    "notlar":   ("/notlar",    "Notlar"),
    "notes":    ("/notes",     "Notes"),
}


def translation_pairs() -> dict[str, str]:
    """Notes that exist in both languages, keyed by address without extension.

    Each side names the other in its front matter:

        translation: notes/sensory-attenuation

    Both sides have to name each other. A one-way declaration is a typo rather
    than a translation, and publishing an hreflang the other page never confirms
    is worse than publishing none, so a mismatch fails the build.

    A declaration whose counterpart has not been written yet is not an error.
    The Turkish notes already carry the address their translation will have, so
    the pairing is settled before anyone sits down to translate.
    """
    declared = {}
    for d in ("notlar", "notes"):
        if not (ROOT / d).is_dir():
            continue
        for qmd in sorted((ROOT / d).glob("*.qmd")):
            m = re.search(r'^translation:\s*["\']?([^"\'\s#]+)',
                          qmd.read_text(encoding="utf-8"), re.M)
            if m:
                key = qmd.relative_to(ROOT).with_suffix("").as_posix()
                declared[key] = m.group(1).strip("/")

    pairs = {}
    for src, dst in declared.items():
        if dst not in declared:
            continue                      # counterpart not written yet
        if declared[dst] != src:
            sys.exit(f"translation mismatch: {src} names {dst}, "
                     f"but {dst} names {declared[dst]}")
        pairs[src] = dst
    return pairs


def page_lang(rel: str) -> str:
    """The lang: a note declares in its own front matter."""
    src = ROOT / f"{rel}.qmd"
    if src.exists():
        m = re.search(r"^lang:\s*([A-Za-z-]+)", src.read_text(encoding="utf-8"), re.M)
        if m:
            return m.group(1)
    return "en"


def write_hreflang(path: Path, base: str, pairs: dict[str, str]) -> bool:
    """Declare that two addresses are the same note in two languages.

    Both members of a pair have to be listed on both pages, the page itself
    included, or the annotation is discarded. x-default points at the English
    side, since that is the language the rest of the site is written in and the
    one a reader with no matching preference should land on.
    """
    rel = path.relative_to(OUT).with_suffix("").as_posix()
    other = pairs.get(rel)
    if not other:
        return False
    text = path.read_text(encoding="utf-8")
    if 'rel="alternate"' in text:
        return False

    sides = sorted({rel, other}, key=page_lang)
    tags = "".join(f'<link rel="alternate" hreflang="{page_lang(r)}" '
                   f'href="{base}/{r}">\n' for r in sides)
    default = next((r for r in sides if page_lang(r) == "en"), rel)
    tags += f'<link rel="alternate" hreflang="x-default" href="{base}/{default}">\n'

    path.write_text(text.replace("</head>", tags + "</head>", 1), encoding="utf-8")
    return True


# Quarto ships these on every page whether the feature is used or not. Measured
# on this site: zero icons, zero code blocks, zero tabsets, and no footnotes or
# cross-references, which are the only things that ever call tippy. The three
# stylesheets are render-blocking, so they delay first paint for nothing.
#
# clipboard.min.js stays. Quarto's inline script calls `new window.ClipboardJS`
# unconditionally, so removing it throws before the code that opens external
# links in a new window.
UNUSED_ASSETS = (
    "bootstrap-icons.css",              # 97 KB, no icon is used anywhere
    "quarto-syntax-highlighting",       # no code blocks
    "tippy.css",                        # no tooltips
    "tippy.umd.min.js",
    "popper.min.js",                    # only there for tippy
    "tabsets/tabsets.js",               # no tabsets
)


# Addresses that were published and then renamed. They stay reachable forever:
# an address that has been out in the world once cannot 404 later, and a static
# host has no server-side redirect, so the redirect has to be a page.
#
# Renamed 2026-08-03. The originals were bare topic names, which would collide
# with the second study on the same topic; every research address now names the
# question rather than the illness.
REDIRECTS = {
    "research/schizophrenia.html": "/research/belief-updating-schizophrenia",
    "research/akathisia.html":     "/research/akathisia-active-inference",
    "research/gambling.html":      "/research/gambling-cognitions",
}


def write_redirects(base: str) -> int:
    """Leave a forwarding page at each retired address."""
    written = 0
    for old, new in REDIRECTS.items():
        path = OUT / old
        if path.exists() and "http-equiv" not in path.read_text(encoding="utf-8"):
            continue                      # a real page lives here; never clobber it
        path.parent.mkdir(parents=True, exist_ok=True)
        # noindex so post-render leaves its canonical alone and the wrapper keeps
        # it out of the sitemap and both LLM indexes. The canonical still points
        # at the new address, which is what tells a crawler the two are one page.
        path.write_text(
            "<!DOCTYPE html>\n"
            '<html lang="en"><head><meta charset="utf-8">\n'
            f'<link rel="canonical" href="{base}{new}">\n'
            '<meta name="robots" content="noindex, follow">\n'
            f'<meta http-equiv="refresh" content="0; url={new}">\n'
            "<title>Moved</title></head>\n"
            f'<body><p>This page is now at <a href="{new}">{base}{new}</a>.</p></body>\n'
            "</html>\n",
            encoding="utf-8", newline="\n")
        written += 1
    return written


def strip_unused_assets(path: Path) -> int:
    """Drop the stylesheets and scripts nothing on this site uses."""
    text = original = path.read_text(encoding="utf-8")
    for name in UNUSED_ASSETS:
        text = re.sub(rf'[ \t]*<link[^>]*{re.escape(name)}[^>]*>\n?', "", text)
        text = re.sub(rf'[ \t]*<script[^>]*{re.escape(name)}[^>]*>\s*</script>\n?', "", text)
    if text == original:
        return 0
    path.write_text(text, encoding="utf-8")
    return sum(1 for n in UNUSED_ASSETS if n in original and n not in text)


def write_breadcrumb(path: Path, base: str) -> bool:
    """Give subdirectory pages a BreadcrumbList.

    Unlike DefinedTermSet, this one Google does render, as the trail shown under
    a result instead of the bare URL. The site is three levels deep in places and
    was publishing none of that structure.

    Only for pages inside a section: the homepage and the root-level pages are
    their own top level and a one-item trail says nothing.
    """
    rel = path.relative_to(OUT).as_posix()
    if "/" not in rel or rel.endswith("/index.html"):
        return False
    section = rel.split("/", 1)[0]
    if section not in SECTIONS:
        return False

    text = path.read_text(encoding="utf-8")
    if '"BreadcrumbList"' in text:
        return False
    title = re.search(r"<title>(.*?)</title>", text, re.S)
    if not title:
        return False
    # The site appends " – Furkan Bekdemir"; the trail wants the page's own name.
    leaf = title.group(1).rsplit("–", 1)[0].strip()
    sec_url, sec_name = SECTIONS[section]

    block = json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Furkan Bekdemir",
             "item": f"{base}/"},
            {"@type": "ListItem", "position": 2, "name": sec_name,
             "item": f"{base}{sec_url}"},
            {"@type": "ListItem", "position": 3, "name": leaf},
        ],
    }, ensure_ascii=False, indent=2)

    path.write_text(
        text.replace("</head>", f'<script type="application/ld+json">\n{block}\n</script>\n</head>', 1),
        encoding="utf-8")
    return True


def write_build_id() -> str:
    """Publish a stamp that changes whenever any page's content changes.

    publish.py waits for this to appear before telling IndexNow anything, and it
    needs a signal that moves on every build. The sitemap does not: edit a page
    without adding an address and it is byte-identical, so a deploy that had not
    landed yet would read as finished.

    Hashing the rendered HTML rather than the sources, because that is what the
    deploy actually serves.
    """
    h = hashlib.sha256()
    for p in sorted(OUT.rglob("*.html")):
        if "site_libs" in p.parts:
            continue
        h.update(p.read_bytes())
    stamp = h.hexdigest()[:16]
    (OUT / "build-id.txt").write_text(stamp + "\n", encoding="utf-8", newline="\n")
    return stamp


def write_defined_terms(path: Path, base: str) -> int:
    """Describe a glossary page as schema.org DefinedTermSet.

    Built from the rendered HTML rather than written into the source, so the
    terms have one home. A JSON-LD copy maintained by hand drifts the first time
    a term is added and nothing reports the drift.

    Google lists no rich result for DefinedTermSet, so this is not a ranking
    play. It is there so a machine reading the page can tell that it holds
    seventy defined terms rather than two thousand words of Turkish prose.

    Deliberately narrow: DefinedTerm descends from Intangible, not CreativeWork,
    so inLanguage, citation and additionalProperty are all invalid on it. The
    language is declared once on the set, and the source stays out of the graph.
    """
    text = path.read_text(encoding="utf-8")
    terms = []
    for sec in re.findall(r'<section id="([^"]+)" class="[^"]*\bterm\b[^"]*">(.*?)</section>',
                          text, re.S):
        anchor, body = sec
        name = re.search(r"<h3[^>]*>(.*?)</h3>", body, re.S)
        if not name:
            continue
        strip = re.search(r"<p>(.*?)</p>", body, re.S)
        plain = lambda s: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()

        term = {"@type": "DefinedTerm",
                "inDefinedTermSet": f"{base}/notlar/terimler#sozluk",
                "name": plain(name.group(1))}
        if strip:
            meta = strip.group(1)
            status = re.search(r'<span class="status[^"]*">(.*?)</span>', meta, re.S)
            head = plain(re.sub(r'<span class="status.*', "", meta, flags=re.S))
            abbr = re.match(r"\(([^)]+)\)", head)
            if abbr:
                term["termCode"] = abbr.group(1)
                head = head[abbr.end():]
            turkish = [t for t in (p.strip(" ·") for p in head.split("·")) if t]
            if turkish:
                term["alternateName"] = turkish[0] if len(turkish) == 1 else turkish
            if status:
                term["description"] = f"Durum: {plain(status.group(1))}."
        term["url"] = f"{base}/notlar/terimler#{anchor}"
        terms.append(term)

    if not terms:
        return 0

    block = json.dumps({
        "@context": "https://schema.org",
        "@type": "DefinedTermSet",
        "@id": f"{base}/notlar/terimler#sozluk",
        "url": f"{base}/notlar/terimler",
        "name": "Hesaplamalı psikiyatri ve sinirbilim terimlerinin Türkçe karşılıkları",
        "inLanguage": "tr",
        "hasDefinedTerm": terms,
    }, ensure_ascii=False, indent=2)

    tag = f'<script type="application/ld+json">\n{block}\n</script>\n'
    if tag in text:
        return 0
    text = text.replace("</head>", tag + "</head>", 1)
    path.write_text(text, encoding="utf-8")
    return len(terms)


def canonical_for(html_path: Path, base: str) -> str:
    """Extensionless URLs, because they outlive the generator that made them.
    Once ORCID or a paper cites an address it can never move, and it must not
    depend on the pages still being .html files."""
    rel = html_path.relative_to(OUT).as_posix()
    if rel.endswith("/index.html"):
        rel = rel[: -len("index.html")]          # a/index.html -> a/
    elif rel == "index.html":
        rel = ""
    else:
        rel = rel[: -len(".html")]               # cv.html -> cv
    return f"{base}/{rel}"


def is_quarto_page(text: str) -> bool:
    """Only pages Quarto rendered are ours to rewrite. A file copied in as a
    resource, such as a search-engine ownership check, has to reach the browser
    exactly as written, or the thing checking it fails."""
    return bool(re.search(r'<meta name="generator" content="quarto-', text, re.I))


def is_doorway(text: str) -> bool:
    """A page that asks not to be indexed has its own reason for the canonical
    it carries; rewriting it would undo that."""
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

    path.write_text(text, encoding="utf-8", newline="\n")
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
        path.write_text(text, encoding="utf-8", newline="\n")
    return done


def scope_jsonld(path: Path) -> bool:
    """head.html is global, so its ProfilePage schema lands on every page.
    Only the homepage is a profile; the rest are ordinary pages about it."""
    # By path, not by name: a section index is not the profile page.
    # ProfilePage belongs on the pages that are about the person: the homepage
    # and the CV. Everywhere else the person is the author, not the subject, so
    # the page is a WebPage and the Person moves from mainEntity to about.
    if path in (OUT / "index.html", OUT / "cv.html"):
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


# robots.txt is written by site-post-render.py, which runs this file and then
# applies the crawler policy. There used to be a second writer here, granting
# ai-train=yes and allowing every training crawler. It was overwritten moments
# later by the opposite policy, so the published file was right, but only
# because of the order the two ran in. One writer, and it is the one that
# decides.


def main() -> None:
    if not OUT.is_dir():
        sys.exit(f"output dir not found: {OUT}")

    base = site_url()
    # rglob, not glob: a page in a subdirectory needs a canonical just as much,
    # and would otherwise be skipped without a word.
    pages = sorted(p for p in OUT.rglob("*.html") if "site_libs" not in p.parts)
    changed, failed, deferred, fixes, scoped, defined, crumbs, stripped = [], [], 0, set(), 0, 0, 0, 0
    pairs, alts = translation_pairs(), 0

    for p in pages:
        text = p.read_text(encoding="utf-8")
        if not is_quarto_page(text):
            continue
        # Only the canonical is a doorway's own business. A noindex page still
        # needs its schema narrowed, or the 404 declares itself the profile
        # page, and it still needs its scripts deferred and its labels fixed.
        if not is_doorway(text):
            result = inject_canonical(p, base)
            if result is None:
                failed.append(p.name)
            elif result:
                changed.append(p.name)
        deferred += defer_head_scripts(p)
        fixes.update(fix_a11y(p))
        scoped += scope_jsonld(p)
        defined += write_defined_terms(p, base)
        crumbs += write_breadcrumb(p, base)
        alts += write_hreflang(p, base, pairs)
        stripped += strip_unused_assets(p)

    print(f"canonical: {len(changed)}/{len(pages)} page(s) updated"
          + (f" ({', '.join(changed)})" if changed else ""))
    if deferred:
        print(f"defer: {deferred} script tag(s)")
    if fixes:
        print("a11y: " + ", ".join(sorted(fixes)))
    if scoped:
        print(f"json-ld: {scoped} page(s) narrowed to WebPage")
    if defined:
        print(f"json-ld: {defined} term(s) described as DefinedTermSet")
    if crumbs:
        print(f"json-ld: {crumbs} page(s) given a breadcrumb trail")
    if alts:
        print(f"hreflang: {alts} page(s) paired with a translation")
    if stripped:
        print(f"assets: {stripped} unused reference(s) removed")
    moved = write_redirects(base)
    if moved:
        print(f"redirects: {moved} retired address(es) still resolve")
    if normalise_sitemap(base):
        print("sitemap: index.html -> /, duplicates dropped")
    stamp = write_build_id()
    print(f"build id: {stamp}")
    if write_llms_txt(base):
        print("llms.txt + llms-full.txt: written")

    index = OUT / "search.json"
    if index.exists() and not search_enabled():
        index.unlink()
        print("search.json: removed (search disabled)")

    if failed:
        sys.exit("no </head> in: " + ", ".join(failed))


if __name__ == "__main__":
    main()
