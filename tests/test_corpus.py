"""The cleaning decides what the retriever can match. Each rule here came from reading a real page."""

from docs_rag.corpus import is_included, load_doc, plain


def test_heading_anchor_is_dropped():
    assert plain("## Additional validation { #additional-validation }") == "## Additional validation"


def test_box_markers_become_a_label():
    assert plain("/// tip\n\nUse Query.\n\n///") == "Tip:\n\nUse Query."


def test_box_title_is_kept():
    assert plain("/// note | Technical Details\n\nStarlette.\n\n///") == "Technical Details\n\nStarlette."


def test_link_keeps_its_words_and_loses_the_url():
    assert plain("See the [Python Types Intro](../python-types.md#type-hints).") == "See the Python Types Intro."


def test_html_tags_go_and_their_words_stay():
    assert plain('<abbr title="also known as">a.k.a.</abbr> fast <img src="/img/x.png">') == "a.k.a. fast"


def test_bold_markers_go():
    assert plain("**FastAPI** will know") == "FastAPI will know"


def test_included_code_is_pasted_in(tmp_path):
    docs = tmp_path / "docs" / "en" / "docs"
    (docs / "tutorial").mkdir(parents=True)
    (tmp_path / "docs_src").mkdir()
    (tmp_path / "docs_src" / "app.py").write_text("app = FastAPI()\n")
    page = docs / "tutorial" / "first.md"
    page.write_text("Make an app:\n\n{* ../../docs_src/app.py hl[1] *}\n")

    doc = load_doc(page, docs)

    assert doc.path == "tutorial/first.md"
    assert "app = FastAPI()" in doc.text
    assert "{*" not in doc.text


def test_pages_about_the_project_are_left_out():
    assert not is_included("release-notes.md")
    assert not is_included("reference/fastapi.md")
    assert is_included("tutorial/first-steps.md")