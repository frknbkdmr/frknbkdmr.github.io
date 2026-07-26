"""Build the 1200x630 social card.

Uses the site's own palette and type, and the actual trace from index.qmd
rather than a decorative squiggle — the README calls that figure a real trace,
so the card should not quietly replace it with a drawn line.
"""
import os
import re
import urllib.request
from PIL import Image, ImageDraw, ImageFont

SITE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(SITE, ".ttf-cache")   # gitignored; TTFs are fetched, not stored
W, H = 1200, 630

GROUND = (247, 248, 247)
INK = (20, 24, 28)
INK_SOFT = (90, 100, 110)
RULE = (217, 222, 220)
SIGNAL = (29, 92, 138)
ERROR = (156, 82, 32)

# Straight from IBM's own repository. Google Fonts negotiates format by
# user-agent and hands an old one EOT, which Pillow cannot read; the source
# repo just serves TTF.
PLEX = ("https://raw.githubusercontent.com/IBM/plex/master/packages/"
        "plex-{pkg}/fonts/complete/ttf/IBMPlex{Fam}-{style}.ttf")


def get_ttf(pkg: str, fam: str, style: str) -> str:
    os.makedirs(CACHE, exist_ok=True)
    name = f"IBMPlex{fam}-{style}.ttf"
    path = os.path.join(CACHE, name)
    if not os.path.exists(path):
        url = PLEX.format(pkg=pkg, Fam=fam, style=style)
        data = urllib.request.urlopen(url, timeout=90).read()
        if not data.startswith(b"\x00\x01\x00\x00"):
            raise SystemExit(f"{name} is not a TTF: {data[:6]!r}")
        with open(path, "wb") as f:
            f.write(data)
    return path


def path_points(d: str):
    """Pull the x y pairs out of an SVG path of M/L commands."""
    nums = [float(n) for n in re.findall(r"-?\d+\.?\d*", d)]
    return list(zip(nums[0::2], nums[1::2]))


def load_trace():
    src = open(os.path.join(SITE, "index.qmd"), encoding="utf-8").read()
    out = {}
    for cls in ("t-band", "t-truth", "t-line"):
        m = re.search(rf'class="{cls}"[^>]*\sd="([^"]+)"', src)
        if not m:
            raise SystemExit(f"{cls} path not found in index.qmd")
        out[cls] = path_points(m.group(1))
    return out


def main():
    serif = ImageFont.truetype(get_ttf("serif", "Serif", "Medium"), 82)
    sans = ImageFont.truetype(get_ttf("sans", "Sans", "Regular"), 30)
    mono = ImageFont.truetype(get_ttf("mono", "Mono", "Regular"), 21)

    SS = 2  # supersample, then downscale for clean edges
    img = Image.new("RGB", (W * SS, H * SS), GROUND)
    d = ImageDraw.Draw(img, "RGBA")

    M = 84 * SS                      # left margin
    d.text((M, 150 * SS), "Furkan Bekdemir", font=serif, fill=INK, anchor="ls")
    d.text((M, 205 * SS), "Psychiatry · Computational modelling · Instrumentation",
           font=sans, fill=INK_SOFT, anchor="ls")

    d.line([(M, 250 * SS), (W * SS - M, 250 * SS)], fill=RULE, width=1 * SS)
    d.text((M, 288 * SS), "FURKANBEKDEMIR.COM", font=mono, fill=INK_SOFT, anchor="ls")

    # Fit the trace to its actual data bounds rather than its viewBox: the
    # figure leaves slack inside the box, which on a card reads as the image
    # having stopped early.
    tr = load_trace()
    allpts = [p for pts in tr.values() for p in pts]
    xs = [p[0] for p in allpts]
    ys = [p[1] for p in allpts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)

    box_l, box_r = M, W * SS - M
    box_t, box_b = 330 * SS, (H - 84) * SS
    sx = (box_r - box_l) / (x1 - x0)
    sy = (box_b - box_t) / (y1 - y0)

    def to_px(pts):
        return [(box_l + (px - x0) * sx, box_t + (py - y0) * sy) for px, py in pts]

    d.polygon(to_px(tr["t-band"]), fill=(*SIGNAL, 33))

    truth = to_px(tr["t-truth"])
    for i in range(0, len(truth) - 1, 2):          # dashed
        d.line([truth[i], truth[i + 1]], fill=(*ERROR, 205), width=2 * SS)

    line = to_px(tr["t-line"])
    d.line(line, fill=SIGNAL, width=3 * SS, joint="curve")

    img = img.resize((W, H), Image.LANCZOS)
    out = os.path.join(SITE, "og-image.png")
    img.save(out, "PNG", optimize=True)
    print(f"  og-image.png: {os.path.getsize(out):,} B  ({W}x{H})")


if __name__ == "__main__":
    main()
