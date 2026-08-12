"""Reflow over-long prose lines in .qmd sources, and nothing else.

    python rewrap.py                 # every page under notlar/, notes/ and the indexes
    python rewrap.py notlar/x.qmd    # named files only

Editing a sentence in the middle of a wrapped paragraph leaves one line far past
the margin. This puts that paragraph back to WIDTH, so a later diff shows the
sentence that changed rather than the whole block reflowing around it.

It rewrites whitespace and nothing else. Two invariants enforce that, and a file
that fails either is left untouched:

1. The fence lines come out identical. An earlier version of this script decided
   whether a block was prose by looking at its first line only, so a block that
   opened with a sentence and ended with a bare ::: was joined into one
   paragraph with the fence glued to the last word. Pandoc then read the fence
   as ordinary text, six ::: {.term} blocks never closed, and the glossary
   rendered 64 boxes for 70 headings. That is the bug this check exists for, and
   the token-sequence check below does not catch it: ". :::" and ".\\n:::"
   normalise to the same tokens.
2. The token sequence comes out identical, which catches a word being dropped or
   duplicated.
"""
import pathlib
import re
import sys
import textwrap

WIDTH = 80
LIMIT = 88          # only reflow a paragraph that actually overshoots
DEFAULT = ["notlar.qmd", "notes.qmd"]
# The glossary writes each entry's comment as a single long line and has done
# since it was written. Reflowing it is a two-hundred-line diff that changes no
# content, so it stays out of the default sweep; name it on the command line if
# you ever do want it wrapped.
SKIP = {"notlar/terimler.qmd"}

# A line that opens or closes a Quarto fenced div, at any indentation.
FENCE = re.compile(r"^\s*:::")
# Blocks that are never prose: front matter, headings, raw HTML, comments,
# tables, lists. Checked per line, not per block.
NOT_PROSE = ("---", "#", "```", "<!--", "|", "-", "*", ">", "    ")


def fence_lines(text: str) -> list[str]:
    return [l.strip() for l in text.splitlines() if FENCE.match(l)]


def tokens(text: str) -> str:
    return " ".join(text.split())


def reflow_block(block: str) -> str:
    """Reflow one blank-line-delimited block, keeping its fences on own lines."""
    lines = block.splitlines()

    # Peel fences off both ends; they are structure, never part of a paragraph.
    head, tail = [], []
    while lines and FENCE.match(lines[0]):
        head.append(lines.pop(0))
    while lines and FENCE.match(lines[-1]):
        tail.insert(0, lines.pop())

    body = "\n".join(lines)
    # A fence still inside means the block is not a single paragraph. Leave it.
    if any(FENCE.match(l) for l in lines):
        return block
    if not body.strip():
        return block
    if body.lstrip().startswith(NOT_PROSE):
        return block
    if max((len(l) for l in lines), default=0) <= LIMIT:
        return block

    wrapped = textwrap.fill(re.sub(r"\s*\n\s*", " ", body).strip(), width=WIDTH,
                            break_long_words=False, break_on_hyphens=False)
    return "\n".join(head + [wrapped] + tail)


def rewrap(text: str) -> str:
    fm = re.match(r"^---\n.*?\n---\n", text, re.S)
    head, rest = (fm.group(0), text[fm.end():]) if fm else ("", text)

    # Raw HTML blocks hold JSON-LD and hand-drawn SVG; both break if reflowed.
    guards: list[str] = []

    def stash(m):
        guards.append(m.group(0))
        return f"\x00G{len(guards) - 1}\x00"

    rest = re.sub(r"```\{=html\}.*?```", stash, rest, flags=re.S)
    rest = "\n\n".join(reflow_block(b) for b in rest.split("\n\n"))
    for i, g in enumerate(guards):
        rest = rest.replace(f"\x00G{i}\x00", g)
    return head + rest


def main(argv: list[str]) -> int:
    if argv:
        paths = [pathlib.Path(a) for a in argv]
    else:
        root = pathlib.Path(__file__).parent
        paths = [root / n for n in DEFAULT]
        for d in ("notlar", "notes"):
            paths += sorted((root / d).glob("*.qmd"))
        paths = [p for p in paths if p.exists()
                 and p.relative_to(root).as_posix() not in SKIP]

    failed = changed = 0
    for p in paths:
        before = p.read_text(encoding="utf-8")
        after = rewrap(before)
        if fence_lines(after) != fence_lines(before):
            print(f"{p}: FENCE DEĞİŞTİ, yazılmadı")
            failed += 1
            continue
        if tokens(after) != tokens(before):
            print(f"{p}: METİN DEĞİŞTİ, yazılmadı")
            failed += 1
            continue
        if after != before:
            p.write_text(after, encoding="utf-8", newline="\n")
            n = sum(1 for l in before.splitlines() if len(l) > LIMIT)
            print(f"{p}: {n} uzun satır sarıldı")
            changed += 1

    print(f"{len(paths)} dosya, {changed} değişti, {failed} reddedildi")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
