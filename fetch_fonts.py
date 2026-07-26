"""Self-host the IBM Plex faces the site actually uses.

Fetches the Google Fonts CSS with a modern UA (so we get woff2, not ttf),
downloads every latin / latin-ext face, and rewrites the CSS to point at the
local copies. Only the weights the stylesheet actually asks for are taken.
"""
import hashlib
import os
import re
import urllib.request

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

CSS_URL = (
    "https://fonts.googleapis.com/css2"
    "?family=IBM+Plex+Mono:wght@400;500"
    "&family=IBM+Plex+Sans:ital,wght@0,400;0,500;1,400"
    "&family=IBM+Plex+Serif:wght@400;500"
    "&display=swap"
)

# Turkish needs latin-ext (ğ, ş, İ, ı); keep latin too.
WANTED_SUBSETS = {"latin", "latin-ext"}


def get(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    return data if binary else data.decode("utf-8")


def main():
    os.makedirs(OUT, exist_ok=True)
    css = get(CSS_URL)

    # Google prefixes each @font-face with a /* subset */ comment.
    blocks = re.split(r"/\*\s*([a-z0-9-]+)\s*\*/", css)
    pairs = [(blocks[i], blocks[i + 1]) for i in range(1, len(blocks) - 1, 2)]

    out_css, seen, by_digest, sizes = [], {}, {}, {}
    for subset, block in pairs:
        if subset not in WANTED_SUBSETS:
            continue
        m = re.search(r"src:\s*url\((https://[^)]+\.woff2)\)", block)
        if not m:
            continue
        url = m.group(1)
        fam = re.search(r"font-family:\s*'([^']+)'", block).group(1)
        wght = re.search(r"font-weight:\s*(\d+)", block).group(1)
        style = re.search(r"font-style:\s*(\w+)", block).group(1)

        name = f"{fam.replace(' ', '')}-{wght}{'i' if style == 'italic' else ''}-{subset}.woff2"
        if name in seen:
            name = seen[name]
        else:
            data = get(url, binary=True)
            digest = hashlib.md5(data).hexdigest()
            # Google serves one physical file for several declared weights of
            # some families; store it once and let both faces point at it.
            if digest in by_digest:
                seen[name] = by_digest[digest]
                name = by_digest[digest]
            else:
                with open(os.path.join(OUT, name), "wb") as f:
                    f.write(data)
                by_digest[digest] = name
                sizes[name] = len(data)
                seen[name] = name

        out_css.append(
            re.sub(r"src:\s*url\([^)]+\)", f"src: url(./{name})", block.strip())
            .replace("@font-face", f"/* {subset} */\n@font-face")
        )

    header = (
        "/* IBM Plex, self-hosted.\n"
        "   Served from this origin so no visitor IP reaches a third party, and\n"
        "   so the render-blocking chain has one fewer host to resolve.\n"
        "   Regenerate with `python fetch_fonts.py` if a weight is added. */\n\n"
    )
    with open(os.path.join(OUT, "fonts.css"), "w", encoding="utf-8") as f:
        f.write(header + "\n\n".join(out_css) + "\n")

    total = sum(sizes.values())
    for n, s in sorted(sizes.items()):
        print(f"  {n}: {s:,} B")
    print(f"\n{len(sizes)} files, {total:,} B total ({total/1024:.0f} KB)")


if __name__ == "__main__":
    main()
