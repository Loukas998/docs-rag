"""The documents the system answers from: FastAPI's English docs at one release, as plain text.

    uv run python -m docs_rag.corpus fetch      # once: downloads the pinned release into corpus/
    uv run python -m docs_rag.corpus stats
    uv run python -m docs_rag.corpus show advanced/opentelemetry.md

The corpus is data, like the golden set: one pinned version, checked by SHA-256, so every run and
every quote in the golden set refers to the same text.
"""


import hashlib
from imaplib import Time2Internaldate
import io
from os import path
import re
import sys
import tarfile
import urllib.request
from pathlib import Path

from pydantic import BaseModel, ConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

FASTAPI_VERSION = "0.162.0"
CORPUS_NAME = f"fastapi-{FASTAPI_VERSION}"
TARBALL_URL = f"https://github.com/fastapi/fastapi/archive/refs/tags/{FASTAPI_VERSION}.tar.gz"
TARBALL_SHA256 = "740d83d44f6f6a17c8759b2f3cd2d04f1eeade97ddf540700f9e2a107537f022"

CORPUS_DIR = PROJECT_ROOT / "corpus" / CORPUS_NAME
DOCS_DIR = CORPUS_DIR / "docs" / "en" / "docs"

# Pages that are not about using FastAPI, or whose markdown has almost no text. Decided once, here.
EXCLUDED = {
    "release-notes.md",  # a changelog: 58,000 words of one-line PR titles, a third of all the text
    "_llm-test.md", "fastapi-people.md", "external-links.md", "newsletter.md", "management.md",
    "translation-banner.md", "translations.md", "contributing.md", "help-fastapi.md",
}
EXCLUDED_DIRS = ("reference/",) # filled from docstrings at build time; the markdown is `::: fastapi.FastAPI`


class Doc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    """Relative to the docs folder, e.g. "tutorial/first-steps.md". The page's URL is built from it."""
    text: str
    """Plain text with the code examples put back in. Markdown headings are kept: a later chunker splits on them."""
 

# {* ../../docs_src/first_steps/tutorial001_py310.py hl[3] *} and {!> ../../docs_src/x.py!} — the docs
# keep their code in separate files and paste it in when the site is built. The path is relative to docs/en.
# Options like ln[14:18] (show only some lines) are ignored: the whole file goes in, a superset of the page.
INCLUDE = re.compile(r"\{\*\s*(\.\./\S+)[^*]*\*\}|\{!>?\s*(\.\./[^!\s]+)\s*!\}")


def resolve_includes(markdown: str, docs_root: Path) -> str:
    """Paste each included code file in as a fenced block, the way the website shows it."""
    base = docs_root.parent # docs/en

    def paste(match: re.Match[str]) -> str:
        source = base / (match.group(1) or match.group(2))
        return "```\n" + source.read_text().strip() + "\n```"

    return INCLUDE.sub(paste, markdown)


def box_label(match: re.Match[str]) -> str:
    """"/// tip" → "Tip:" · "/// note | Technical Details" → "Technical Details" · a closing "///" → nothing."""
    kind, title = match.group(1), match.group(2)
    if title:
        return title
    return f"{kind.capitalize()}:" if kind else ""


def plain(markdown: str) -> str:
    """Markdown → the text a reader sees. Used on the docs and on golden-set quotes alike, so they compare."""
    text = re.sub(r"[ \t]*\{\s*#[\w-]+\s*\}", "", markdown)  # heading anchors: "## Title { #title }"
    text = re.sub(r"(?m)^////?[ \t]*(\w+)?[ \t]*(?:\|[ \t]*(.*))?$", box_label, text)  # "/// tip" … "///"
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)  # images
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)  # links keep their words, lose the URL
    text = re.sub(r"<img[^>]*>|</?[a-zA-Z][^>]*>", "", text)  # HTML tags; the words between them stay
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # bold
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def load_doc(path: Path, docs_root: Path = DOCS_DIR) -> Doc:
    return Doc(path=path.relative_to(docs_root).as_posix(), text=plain(resolve_includes(path.read_text(), docs_root)))


def is_included(relative: str) -> bool:
    """False for a page in EXCLUDED or under one of EXCLUDED_DIRS; True for every other page."""
    return False if relative in EXCLUDED or relative.startswith(EXCLUDED_DIRS) else True


def load_corpus(docs_root: Path = DOCS_DIR) -> list[Doc]:
    if not docs_root.exists():
        return SystemExit(f"no corpus at {docs_root} - run: uv run python -m docs_rag.corpus fetch")
    paths = sorted(docs_root.rglob("*.md"))
    return [load_doc(p, docs_root) for p in paths if is_included(p.relative_to(docs_root).as_posix())]


def fetch() -> None:
    """Download the pinned release and keep only what the corpus needs: the English docs and the code they include."""
    print(f"downloaing {TARBALL_URL}")
    data = urllib.request.urlopen(TARBALL_URL, timeout=120).read()
    sha = hashlib.sha256(data).hexdigest()
    if sha != TARBALL_SHA256:
        raise SystemExit(f"SHA-256 mismatch: expected {TARBALL_SHA256}, got {sha}. Not using it.")
    
    prefix = f"fastapi-{FASTAPI_VERSION}/"
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        members = []
        for member in tar.getmembers():
            name = member.name.removeprefix(prefix)
            # The pages, and the code they paste in: mostly docs_src/, once a file of FastAPI itself.
            if (name.startswith("docs/en/docs/") and name.endswith(".md")) or name.startswith(("docs_src/", "fastapi/")):
                member.name = name
                members.append(member)
            tar.extractall(CORPUS_DIR, members=members, filter="data") # "data" refuses paths that escape the folder
    print(f"saved {len(members)} files to {CORPUS_DIR.relative_to(PROJECT_ROOT)}")



def stats() -> None:
    """Print the page count and total words, then the five longest pages with their word counts."""
    docs = load_corpus()
    words = sum(len(d.text.split()) for d in docs)
    print(f"{CORPUS_NAME}: {len(docs)} pages . {words:,} words")
    for doc in sorted(docs, key=lambda d: len(d.text.split()), reverse=True)[:5]:
        print(f"  {len(doc.text.split()):>6,} words  {doc.path}")



if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "stats"
    if command == "fetch":
        fetch()
    elif command == "stats":
        stats()
    elif command == "show":
        print(load_doc(DOCS_DIR / sys.argv[2]).text)
    else:
        raise SystemExit(f"unknown command {command!r}: use fetch, stats or show <path>")

