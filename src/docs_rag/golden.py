"""The retrieval golden set: questions a user would ask, and the passage in the docs that answers each.

    uv run python -m docs_rag.golden      # checks that every quote really is in its page

A question points at its answer with a quote, not a chunk id. Chunk ids change every time the
chunking changes; a quote from the docs does not. So one golden set scores every chunking.
"""

import re
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from docs_rag.corpus import CORPUS_NAME, PROJECT_ROOT, Doc, load_corpus, plain

GOLDEN_PATH = PROJECT_ROOT / "golden" / "questions.json"

MAX_QUOTE_WORDS = 40
"""Kept below every config's overlap, so a quote always fits wholly inside one chunk."""

Kind = Literal["lookup", "multi-hop", "no-answer"]


def words(text: str) -> str:
    """plain() first, then only the words — letters, digits, underscores — lowercased, one space apart.

    This is what two texts are compared on."""
    return " ".join(re.findall(r"[a-z0-9_]+", plain(text).lower()))



def contains(text: str, quote: str) -> bool:
    """True when `quote` appears in `text` word for word — ignoring case, punctuation and markdown.

    So a quote copied from the website matches the page's markdown: `Query(max_length=50)` and
    Query(max_length=50) are the same words. Whole words only: "max" does not match "max_length".
    """
    return f" {words(quote)} " in f" {words(text)} "


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc: str
    """The page, as `corpus show` takes it: "tutorial/query-params-str-validations.md"."""
    quote: str
    """A short passage copied from that page, which answers the question (or a part of it)."""

    @field_validator("quote")
    @classmethod
    def short_enough(cls, quote: str) -> str:
        """Refuse a quote longer than MAX_QUOTE_WORDS words; return it unchanged otherwise."""
        n = len(quote.split())
        if n > MAX_QUOTE_WORDS:
            raise ValueError(f"quote has {n} words; keep it to {MAX_QUOTE_WORDS} — the sentence that answers, not the paragraph")
        return quote


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    question: str
    answer: str
    """One sentence, your words. Not used to score retrieval; the generation lessons will need it."""
    kind: Kind
    evidence: list[Evidence] = []
    """lookup: any one of these passages answers it (usually there is one).
    multi-hop: every passage is needed, and they come from different pages.
    no-answer: none — the docs do not answer it."""
    notes: str = ""

    @model_validator(mode="after")
    def evidence_fits_kind(self) -> "Question":
        """no-answer: no evidence. lookup: at least one passage. multi-hop: passages from two or more pages."""
        n, pages = len(self.evidence), {e.doc for e in self.evidence}
        if self.kind == "no-answer" and n:
            raise ValueError(f"{self.id}: a no-answer question has no evidence")
        if self.kind == "lookup" and not n:
            raise ValueError(f"{self.id}: a lookup needs at least one passage")
        if self.kind == "multi-hop" and len(pages) < 2:
            raise ValueError(f"{self.id}: multi-hop needs passages from at least two pages")
        return self


class GoldenSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    corpus: str
    """The docs release the quotes were copied from. Quotes are only valid against that text."""
    questions: list[Question]

    @model_validator(mode="after")
    def ids_are_unique(self) -> "GoldenSet":
        ids = [q.id for q in self.questions]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"duplicate question ids: {duplicates}")
        return self


def load(path: Path = GOLDEN_PATH) -> GoldenSet:
    return GoldenSet.model_validate_json(path.read_text())


def problems(golden: GoldenSet, docs: list[Doc]) -> list[str]:
    """Every quote that is not in its page, and every page that does not exist."""
    by_path = {doc.path: doc for doc in docs}
    found = []
    if golden.corpus != CORPUS_NAME:
        found.append(f"golden set is for {golden.corpus}, the corpus is {CORPUS_NAME}")
    for q in golden.questions:
        for e in q.evidence:
            if e.doc not in by_path:
                found.append(f"{q.id}: no page {e.doc!r} (excluded, or a typo?)")
            elif not contains(by_path[e.doc].text, e.quote):
                found.append(f"{q.id}: quote not found in {e.doc}: {e.quote[:60]!r}")
    return found


if __name__ == "__main__":
    golden = load()
    found = problems(golden, load_corpus())
    kinds = {k: sum(q.kind == k for q in golden.questions) for k in ("lookup", "multi-hop", "no-answer")}
    print(f"{len(golden.questions)} questions · " + " · ".join(f"{k} {n}" for k, n in kinds.items()))
    for line in found:
        print(f"  X {line}")
    if found:
        sys.exit(1)
    print("every quote found in its page")