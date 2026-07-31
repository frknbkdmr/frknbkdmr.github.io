"""Run the existing post-render fixes, then apply publication policies.

Search engines and user-initiated AI retrieval remain welcome. Crawlers whose
stated purpose includes model training or general model development are blocked.
Pages carrying ``noindex`` remain directly reachable, but are removed from the
sitemap and the two LLM-readable indexes until they are ready to be discovered.
"""

from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).parent
OUT = ROOT / "_site"
CONFIG = ROOT / "_quarto.yml"

SEARCH_AND_RETRIEVAL_AGENTS = [
    "OAI-SearchBot",
    "ChatGPT-User",
    "Claude-SearchBot",
    "Claude-User",
    "PerplexityBot",
    "Perplexity-User",
]

TRAINING_AGENTS = [
    "GPTBot",
    "ClaudeBot",
    "Google-Extended",
    "CCBot",
    "Applebot-Extended",
    "cohere-ai",
    "Meta-ExternalAgent",
    "Bytespider",
]


def site_url() -> str:
    text = CONFIG.read_text(encoding="utf-8")
    match = re.search(r'^\s*site-url:\s*["\']?([^"\'\s#]+)', text, re.M)
    if not match:
        sys.exit(f"site-url not found in {CONFIG.name}")
    return match.group(1).rstrip("/")


def page_url(path: Path, base: str) -> str:
    """Return the extensionless public URL used by canonical tags and sitemap."""
    rel = path.relative_to(OUT).as_posix()
    if rel == "index.html":
        rel = ""
    elif rel.endswith("/index.html"):
        rel = rel[: -len("index.html")]
    else:
        rel = rel[: -len(".html")]
    return f"{base}/{rel}"


def has_noindex(html: str) -> bool:
    """Recognise a robots noindex directive regardless of attribute order."""
    for tag in re.findall(r"<meta\b[^>]*>", html, flags=re.I):
        if re.search(r'\bname=["\']robots["\']', tag, flags=re.I) and re.search(
            r'\bcontent=["\'][^"\']*\bnoindex\b', tag, flags=re.I
        ):
            return True
    return False


def remove_noindex_from_indexes(base: str) -> list[str]:
    """Remove noindex pages from sitemap.xml, llms.txt and llms-full.txt."""
    hidden = sorted(
        page_url(path, base)
        for path in OUT.rglob("*.html")
        if "site_libs" not in path.parts
        and has_noindex(path.read_text(encoding="utf-8"))
    )
    if not hidden:
        return []

    hidden_set = set(hidden)

    sitemap = OUT / "sitemap.xml"
    if sitemap.exists():
        text = sitemap.read_text(encoding="utf-8")

        def keep_url(match: re.Match[str]) -> str:
            block = match.group(0)
            loc = re.search(r"<loc>(.*?)</loc>", block, flags=re.S)
            return "" if loc and loc.group(1).strip() in hidden_set else block

        text = re.sub(r"[ \t]*<url>.*?</url>\s*", keep_url, text, flags=re.S)
        sitemap.write_text(text, encoding="utf-8", newline="\n")

    llms = OUT / "llms.txt"
    if llms.exists():
        lines = llms.read_text(encoding="utf-8").splitlines()
        lines = [line for line in lines if not any(f"]({url})" in line for url in hidden)]
        llms.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")

    full = OUT / "llms-full.txt"
    if full.exists():
        sections = full.read_text(encoding="utf-8").split("\n---\n")
        sections = [
            section
            for section in sections
            if not any(f"URL: {url}" in section for url in hidden)
        ]
        full.write_text(
            "\n---\n".join(sections).rstrip() + "\n",
            encoding="utf-8",
            newline="\n",
        )

    return hidden


def write_robots(base: str) -> None:
    lines = [
        "# Public pages may be indexed and used for user-initiated retrieval.",
        "# Automated collection for model training or general model development",
        "# is not permitted.",
        "",
        "Content-Signal: search=yes, ai-input=yes, ai-train=no",
        "",
        "User-agent: *",
        "Allow: /",
        "",
        "# Search and user-initiated AI retrieval.",
    ]

    for agent in SEARCH_AND_RETRIEVAL_AGENTS:
        lines.extend([f"User-agent: {agent}", "Allow: /", ""])

    lines.append("# Model-training and general model-development crawlers.")
    for agent in TRAINING_AGENTS:
        lines.extend([f"User-agent: {agent}", "Disallow: /", ""])

    lines.extend([
        "# Machine-readable versions of the public site.",
        f"# {base}/llms.txt",
        f"# {base}/llms-full.txt",
        "",
        f"Sitemap: {base}/sitemap.xml",
        "",
    ])

    OUT.mkdir(exist_ok=True)
    (OUT / "robots.txt").write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> None:
    subprocess.run([sys.executable, str(ROOT / "post-render.py")], check=True)
    base = site_url()
    hidden = remove_noindex_from_indexes(base)
    write_robots(base)
    if hidden:
        print("noindex: removed from sitemap and LLM indexes: " + ", ".join(hidden))
    print("robots.txt: search and AI retrieval allowed; training crawlers blocked")


if __name__ == "__main__":
    main()
