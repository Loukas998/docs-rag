"""A quote either is in its page or it is not. These tests pin down what "is in" means."""

import pytest
from pydantic import ValidationError

from docs_rag.corpus import CORPUS_NAME, Doc
from docs_rag.golden import Evidence, GoldenSet, Question, contains, problems


def test_a_quote_copied_from_the_website_matches_the_markdown():
    markdown = "having `Query(max_length=50)` inside of `Annotated`, we are telling **FastAPI**"
    assert contains(markdown, "having Query(max_length=50) inside of Annotated, we are telling FastAPI")


def test_a_link_keeps_its_words_and_loses_the_url():
    assert contains("see the [Python Types Intro](../python-types.md) page", "the Python Types Intro page")


def test_case_and_line_breaks_do_not_matter():
    assert contains("FastAPI will know\nthat the value", "fastapi will know that the value")


def test_whole_words_only():
    assert not contains("set max_length to 50", "max")


def test_a_quote_longer_than_40_words_is_rejected():
    with pytest.raises(ValidationError):
        Evidence(doc="a.md", quote=" ".join(["word"] * 41))


def test_a_no_answer_question_has_no_evidence():
    with pytest.raises(ValidationError):
        Question(id="q1", question="?", answer="-", kind="no-answer", evidence=[Evidence(doc="a.md", quote="x")])


def test_multi_hop_needs_passages_from_two_pages():
    two_from_one_page = [Evidence(doc="a.md", quote="x"), Evidence(doc="a.md", quote="y")]
    with pytest.raises(ValidationError):
        Question(id="q1", question="?", answer="-", kind="multi-hop", evidence=two_from_one_page)


def test_problems_finds_a_missing_quote_and_a_missing_page():
    golden = GoldenSet(version=1, corpus=CORPUS_NAME, questions=[
        Question(id="q1", question="?", answer="-", kind="lookup", evidence=[Evidence(doc="a.md", quote="not on the page")]),
        Question(id="q2", question="?", answer="-", kind="lookup", evidence=[Evidence(doc="zzz.md", quote="x")]),
        Question(id="q3", question="?", answer="-", kind="lookup", evidence=[Evidence(doc="a.md", quote="the real text")]),
    ])
    found = problems(golden, [Doc(path="a.md", text="This is the real text.")])
    assert [line.split(":")[0] for line in found] == ["q1", "q2"]