"""Run the existing post-render fixes, then apply the site's crawler policy.

Search engines and user-initiated AI retrieval remain welcome. Crawlers whose
stated purpose includes model training or general model development are blocked.
Keeping this as the final post-render step prevents Quarto or post-render.py from
silently restoring the previous site-wide training permission.
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
    write_robots(site_url())
    print("robots.txt: search and AI retrieval allowed; training crawlers blocked")


if __name__ == "__main__":
    main()
